
# 
# Copyright 2013-2015 University of Southern California
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

"""ERMREST URL abstract syntax tree (AST) for data resource path-addressing.

"""
import psycopg2
import web
import traceback
import sys
import re

from ...exception import *
from ... import sanepg2
from ...util import sql_literal
import json

class Api (object):

    def __init__(self, catalog):
        self.catalog = catalog
        self.queryopts = dict()
        self.sort = None
        self.before = None
        self.after = None
        self.http_vary = web.ctx.webauthn2_manager.get_http_vary()
        self.http_etag = None

    def enforce_owner(self, cur, uri=''):
        """Policy enforcement on is_owner.
        """
        if not self.catalog.manager.is_owner(
                        cur, web.ctx.webauthn2_context.attributes):
            raise rest.Forbidden(uri)

    def enforce_read(self, cur, uri=''):
        """Policy enforcement on has_read test.
        """
        if not (self.catalog.manager.has_read(
                        cur, web.ctx.webauthn2_context.attributes) ):
            raise rest.Forbidden(uri)

    def enforce_write(self, cur, uri=''):
        """Policy enforcement on has_write test.
        """
        if not (self.catalog.manager.has_write(
                        cur, web.ctx.webauthn2_context.attributes) ):
            raise rest.Forbidden(uri)

    def enforce_content_read(self, cur, uri=''):
        """Policy enforcement on has_content_read test.
        """
        if not (self.catalog.manager.has_content_read(
                        cur, web.ctx.webauthn2_context.attributes) ):
            raise rest.Forbidden(uri)

    def enforce_content_write(self, cur, uri=''):
        """Policy enforcement on has_content_write test.
        """
        if not (self.catalog.manager.has_content_write(
                        cur, web.ctx.webauthn2_context.attributes) ):
            raise rest.Forbidden(uri)

    def enforce_schema_write(self, cur, uri=''):
        """Policy enforcement on has_schema_write test.
        """
        if not (self.catalog.manager.has_schema_write(
                        cur, web.ctx.webauthn2_context.attributes) ):
            raise rest.Forbidden(uri)

    def with_queryopts(self, qopt):
        self.queryopts = qopt
        return self

    def with_sort(self, sort):
        self.sort = sort
        return self

    def with_before(self, before):
        self.before = before
        if len(before) != len(self.sort):
            raise rest.BadRequest(
                'The "before" page key of length %d does not match the "sort" key of length %d.'
                % (len(before), len(self.sort))
            )
        return self

    def with_after(self, after):
        self.after = after
        if len(after) != len(self.sort):
            raise rest.BadRequest(
                'The "after" page key of length %d does not match the "sort" key of length %d.'
                % (len(after), len(self.sort))
            )
        return self

    def negotiated_limit(self):
        """Determine query result size limit to use."""
        if 'limit' in self.queryopts:
            limit = self.queryopts['limit']
            if str(limit).lower() == 'none':
                limit = None
            else:
                try:
                    limit = int(limit)
                except ValueError, e:
                    raise rest.BadRequest('The "limit" query-parameter requires an integer or the string "none".')
            return limit
        else:
            try:
                limit = web.ctx.ermrest_config.get('default_limit', 100)
                if str(limit).lower() == 'none' or limit is None:
                    limit = None
                else:
                    limit = int(limit)
            except:
                return 100
    
    def set_http_etag(self, version):
        """Set an ETag from version key.

        """
        etag = []

        # TODO: compute source_checksum to help with cache invalidation
        #etag.append( source_checksum )

        if 'cookie' in self.http_vary:
            etag.append( '%s' % web.ctx.webauthn2_context.client )
        else:
            etag.append( '*' )
            
        if 'accept' in self.http_vary:
            etag.append( '%s' % web.ctx.env.get('HTTP_ACCEPT', '') )
        else:
            etag.append( '*' )

        etag.append( '%s' % version )

        self.http_etag = '"%s"' % ';'.join(etag).replace('"', '\\"')

    def parse_client_etags(self, header):
        """Parse header string for ETag-related preconditions.

           Returns dict mapping ETag -> boolean indicating strong
           (true) or weak (false).

           The special key True means the '*' precondition was
           encountered which matches any representation.

        """
        def etag_parse(s):
            strong = True
            if s[0:2] == 'W/':
                strong = False
                s = s[2:]
            return (s, strong)

        s = header
        etags = []
        # pick off one ETag prefix at a time, consuming comma-separated list
        while s:
            s = s.strip()
            # accept leading comma that isn't really valid by spec...
            m = re.match('^,? *(?P<first>(W/)?"([^"]|\\\\")*")(?P<rest>.*)', s)
            if m:
                # found 'W/"tag"' or '"tag"'
                g = m.groupdict()
                etags.append(etag_parse(g['first']))
                s = g['rest']
                continue
            m = re.match('^,? *[*](?P<rest>.*)', s)
            if m:
                # found '*'
                # accept anywhere in list even though spec is more strict...
                g = m.groupdict()
                etags.append((True, True))
                s = g['rest']
                continue
            s = None

        return dict(etags)
        
    def http_check_preconditions(self, method='GET', resource_exists=True):
        failed = False

        match_etags = self.parse_client_etags(web.ctx.env.get('HTTP_IF_MATCH', ''))
        if match_etags:
            if resource_exists:
                if self.http_etag and self.http_etag not in match_etags \
                   and (True not in match_etags):
                    failed = True
            else:
                failed = True
        
        nomatch_etags = self.parse_client_etags(web.ctx.env.get('HTTP_IF_NONE_MATCH', ''))
        if nomatch_etags:
            if resource_exists:
                if self.http_etag and self.http_etag in nomatch_etags \
                   or (True in nomatch_etags):
                    failed = True

        if failed:
            headers={ 
                "ETag": self.http_etag, 
                "Vary": ", ".join(self.http_vary)
            }
            if method == 'GET':
                raise rest.NotModified(headers=headers)
            else:
                raise rest.PreconditionFailed(headers=headers)

    def emit_headers(self):
        """Emit any automatic headers prior to body beginning."""
        #TODO: evaluate whether this function is necessary
        if self.http_vary:
            web.header('Vary', ', '.join(self.http_vary))
        if self.http_etag:
            web.header('ETag', '%s' % self.http_etag)
        
    def perform(self, body, finish):
        def wrapbody(conn, cur):
            try:
                client = web.ctx.webauthn2_context.client
                if type(client) is dict:
                    client = client['id']

                attributes = [
                    a['id'] if type(a) is dict else a
                    for a in web.ctx.webauthn2_context.attributes
                ]
                
                cur.execute("""
SELECT set_config('webauthn2.client', %s, false);
SELECT set_config('webauthn2.attributes', %s, false);
""" % (
    sql_literal(client),
    sql_literal(json.dumps(attributes)),
)
                )
                return body(conn, cur)
            except psycopg2.InterfaceError, e:
                raise rest.ServiceUnavailable("Please try again.")
            
        return web.ctx.ermrest_catalog_pc.perform(wrapbody, finish)
    
    def final(self):
        if self.catalog is not self:
            self.catalog.final()

