
# 
# Copyright 2012-2013 University of Southern California
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""ERMREST REST API mapping layer

This module integrates ERMREST as a web.py application:

   A. Loads an ermrest-config.json from the application working
      directory, i.e. the daemon home directory in a mod_wsgi
      deployment.  This data configures a global_env dictionary
      exported from this module.

   B. Configures a webauthn2.Manager instance for security services

   C. Configures a syslog logger

   D. Implements a Dispatcher class to parse ERMREST URLs and dispatch
      to a parser-constructed abstract syntax tree for each web
      request.

   E. Defines a web.py web_urls dispatch table that can be used to
      generate a WSGI app. This maps the core ERMREST Dispatcher as
      well as webauthn2 APIs under an /authn/ prefix.

The general approach to integrating ERMREST with web.py is to use the
web.py provided web.ctx thread-local storage for request state. This
includes preconfigured state:

  web.ctx.ermrest_request_guid: a random correlation key issued per request
  web.ctx.ermrest_start_time: a timestamp when web dispatch began
  web.ctx.webauthn2_context: authentication context for the web request
  web.ctx.webauthn2_manager: the manager used to get authentication context
  web.ctx.ermrest_request_trace(tracedata): a function to log trace data

The mapping also recognized "out" variables that can communicate
information back out of the dispatched request handler:

  web.ctx.ermrest_request_content_range: content range of response (default -/-)
  web.ctx.ermrest_request_content_type: content type of response (default unknown)

These are used in final request logging.

"""
import logging
from logging.handlers import SysLogHandler
import web
import random
import base64
import datetime
import pytz
import struct
import urllib
import sys
import traceback
import itertools
import psycopg2
import webauthn2

from .apicore import global_env, webauthn2_manager, web_method, registry, catalog_factory
from .url import url_parse_func, ast
from .exception import *

from .registry import get_registry
from .catalog import get_catalog_factory
from .util import negotiated_content_type, urlquote

# expose webauthn REST APIs
webauthn2_handler_factory = webauthn2.RestHandlerFactory(manager=webauthn2_manager)
UserSession = webauthn2_handler_factory.UserSession
UserPassword = webauthn2_handler_factory.UserPassword
UserManage = webauthn2_handler_factory.UserManage
AttrManage = webauthn2_handler_factory.AttrManage
AttrAssign = webauthn2_handler_factory.AttrAssign
AttrNest = webauthn2_handler_factory.AttrNest
Preauth = webauthn2_handler_factory.Preauth

class Dispatcher (object):
    """Helper class to handle parser-based URL dispatch

       Normal web.py dispatch is via regular expressions on a decoded
       URL, but we use a hybrid method:

       1. handle top-level catalog APIs via web_urls dispatched
          through web.py, with a final catch-all handler...

       2. for sub-resources of a catalog, run an LALR(1) parser
          generated by python-ply to parse the undecoded sub-resource
          part of the URL, allowing more precise interpretation of
          encoded and unencoded URL characters for meta-syntax.

    """
    def prepareDispatch(self):
        """computes web dispatch from REQUEST_URI

           with the HTTP method of the request, e.g. GET, PUT...
        """
        uri = web.ctx.env['REQUEST_URI']
        
        try:
            return uri, url_parse_func(uri)
        except (LexicalError, ParseError), te:
            raise rest.BadRequest(str(te))
        except:
            et, ev, tb = sys.exc_info()
            web.debug('got exception "%s" during URI parse' % str(ev),
                      traceback.format_exception(et, ev, tb))
            raise

    @web_method()
    def METHOD(self, methodname):
        ast = None
        try:
            uri, ast = self.prepareDispatch()

            if not hasattr(ast, methodname):
                raise rest.NoMethod()

            astmethod = getattr(ast, methodname)
            result = astmethod(uri)
            if hasattr(result, 'next'):
                # force any transaction deferred in iterator
                try:
                    first = result.next()
                except StopIteration:
                    return result
                return itertools.chain([first], result)
            else:
                return result
        finally:
            if ast is not None:
                ast.final()

    def HEAD(self):
        return self.METHOD('HEAD')

    def GET(self):
        return self.METHOD('GET')
        
    def PUT(self):
        return self.METHOD('PUT')

    def DELETE(self):
        return self.METHOD('DELETE')

    def POST(self):
        return self.METHOD('POST')

def web_urls():
    """Builds and returns the web_urls for web.py.
    """
    urls = (
        # user authentication via webauthn2
        '/authn/session(/[^/]+)', UserSession,
        '/authn/session/?()', UserSession,
        '/authn/password(/[^/]+)', UserPassword,
        '/authn/password/?()', UserPassword,
    
        # user account management via webauthn2
        '/authn/user(/[^/]+)', UserManage,
        '/authn/user/?()', UserManage,
        '/authn/attribute(/[^/]+)', AttrManage,
        '/authn/attribute/?()', AttrManage,
        '/authn/user/([^/]+)/attribute(/[^/]+)', AttrAssign,
        '/authn/user/([^/]+)/attribute/?()', AttrAssign,
        '/authn/attribute/([^/]+)/implies(/[^/]+)', AttrNest,
        '/authn/attribute/([^/]+)/implies/?()', AttrNest,
        '/authn/preauth(/[^/]+)', Preauth,
        '/authn/preauth/?()', Preauth,

        # the catalog factory
        '/catalog/?', ast.Catalogs,
        
        # core parser-based REST dispatcher
        '(?s).*', Dispatcher
    )
    return tuple(urls)
