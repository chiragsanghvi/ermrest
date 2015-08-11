
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

"""ERMREST URL abstract syntax tree (AST) for data resources.

"""

import cStringIO
import web

from .path import Api
from .... import ermpath, exception
from ....ermpath.name import Name
from ....util import negotiated_content_type
    
def _preprocess_attributes(epath, attributes):
    """Expand '*' wildcards in attributes into explicit projections understood by ermpath."""
    results = []
    for item in attributes:
        if type(item) is tuple:
            # make preprocessing resolution idempotent
            attribute, col, base = item
        else:
            attribute = item
            if len(attribute.nameparts) > 2:
                raise exception.BadSyntax('Column name %s, qualified by schema and table names, not allowed as attribute.' % attribute)
            elif len(attribute.nameparts) > 1 and attribute.nameparts[0] not in epath.aliases:
                raise exception.BadSyntax('Alias %s, qualifying column name %s, not bound in path.' % (attribute.nameparts[0], attribute))
            col, base = attribute.resolve_column(epath._model, epath)

        if col.is_star_column() and not hasattr(attribute, 'aggfunc'):
            # expand '*' wildcard sugar as if user referenced each column
            if attribute.alias is not None:
                raise exception.BadSyntax('Wildcard column %s cannot be given an alias.' % attribute)
            if base == epath:
                # columns from final entity path element
                for col in epath._path[epath.current_entity_position()].table.columns_in_order():
                    results.append((Name([col.name]), col, base))
            elif base in epath.aliases:
                # columns from interior path referenced by alias
                for col in epath[base].table.columns_in_order():
                    results.append((Name([base, col.name]).set_alias('%s:%s' % (base, col.name)), col, base))
            else:
                raise NotImplementedError('Unresolvable * column violates program invariants!')
        else:
            results.append((attribute, col, base))
            
    return results

class TextFacet (Api):
    """A specific text facet by textfragment.

       HACK: Parameters for the corresponding AttributeGroupPath query
       are built by the URL parser to avoid circular dependencies in
       the AST sub-modules.

    """

    default_content_type = 'application/json'

    def __init__(self, catalog, filterelem, facetkeys, facetvals):
        Api.__init__(self, catalog)
        self.filterelem = filterelem
        self.facetkeys = facetkeys
        self.facetvals = facetvals
        self.http_vary.add('accept')
        cur = web.ctx.ermrest_catalog_dsn[2]
        self.enforce_content_read(cur)
        self.model = self.catalog.manager.get_model(cur)
        epath = ermpath.EntityPath(self.model)
        epath.set_base_entity(self.model.ermrest_schema.tables['valuemap'])
        epath.add_filter(self.filterelem)
        self.agpath = ermpath.AttributeGroupPath(
            epath,
            _preprocess_attributes(epath, self.facetkeys),
            _preprocess_attributes(epath, self.facetvals)
        )

    def GET(self, uri):
        """Perform HTTP GET of text facet.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn, cur):
            epath = self.agpath.epath
            self.set_http_etag( epath.get_data_version(cur) )
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return None
            return self.agpath.get(conn, cur, content_type=content_type, limit=limit)

        def post_commit(lines):
            self.emit_headers()
            if lines is None:
                return
            web.header('Content-Type', content_type)
            web.ctx.ermrest_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

class Entity (Api):
    """A specific entity set by entitypath."""

    default_content_type = 'application/json'

    def __init__(self, catalog, elem):
        Api.__init__(self, catalog)
        cur = web.ctx.ermrest_catalog_dsn[2]
        self.enforce_content_read(cur)
        self.model = self.catalog.manager.get_model(cur)
        self.epath = ermpath.EntityPath(self.model)
        if len(elem.name.nameparts) == 2:
            table = self.model.schemas[elem.name.nameparts[0]].tables[elem.name.nameparts[1]]
        elif len(elem.name.nameparts) == 1:
            table = self.model.lookup_table(elem.name.nameparts[0])
        else:
            raise exception.BadSyntax('Name %s is not a valid syntax for a table name.' % elem.name)
        self.epath.set_base_entity(table, elem.alias)
        self.http_vary.add('accept')

    def append(self, elem):
        if elem.is_filter:
            self.epath.add_filter(elem)
        elif elem.is_context:
            if len(elem.name.nameparts) > 1:
                raise exception.BadSyntax('Context name %s is not a valid syntax for an entity alias.' % elem.name)
            try:
                alias = self.epath[unicode(elem.name.nameparts[0])].alias
            except KeyError:
                raise exception.BadData('Context name %s is not a bound alias in entity path.' % elem.name)
                
            self.epath.set_context(alias)
        else:
            keyref, refop, lalias = elem.resolve_link(self.model, self.epath)
            self.epath.add_link(keyref, refop, elem.alias, lalias)
            
    def GET(self, uri):
        """Perform HTTP GET of entities.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn, cur):
            self.set_http_etag( self.epath.get_data_version(cur) )
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return None
            self.epath.add_sort(self.sort)
            return self.epath.get(conn, cur, content_type=content_type, limit=limit)

        def post_commit(lines):
            self.emit_headers()
            if lines is None:
                return
            web.header('Content-Type', content_type)
            web.ctx.ermrest_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

    def PUT(self, uri, post_method=False, post_defaults=None):
        """Perform HTTP PUT of entities.
        """
        try:
            in_content_type = web.ctx.env['CONTENT_TYPE'].lower()
            in_content_type = in_content_type.split(";", 1)[0].strip()
        except:
            in_content_type = self.default_content_type

        content_type = negotiated_content_type(default=in_content_type)

        input_data = cStringIO.StringIO(web.ctx.env['wsgi.input'].read())
        
        def body(conn, cur):
            input_data.seek(0) # rewinds buffer, in case of retry
            self.enforce_content_write(cur, uri)
            return self.epath.put(
                conn,
                cur,
                input_data, 
                in_content_type=in_content_type,
                content_type=content_type, 
                allow_existing = not post_method,
                use_defaults = post_defaults
            )

        def post_commit(lines):
            web.header('Content-Type', content_type)
            web.ctx.ermrest_request_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

    def POST(self, uri):
        """Perform HTTP POST of entities.
        """
        defaults = self.queryopts.get('defaults')
        if defaults and type(defaults) is not set:
            # defaults is a single column name from queryopts
            defaults = set([ defaults ])
        else:
            # defaults is already a set of column names from queryopts
            # or it is None
            pass
        return self.PUT(uri, post_method=True, post_defaults=defaults)

    def DELETE(self, uri):
        """Perform HTTP DELETE of entities.
        """
        def body(conn, cur):
            self.enforce_content_write(cur, uri)
            self.epath.delete(conn, cur)

        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)


class Attribute (Api):
    """A specific attribute set by attributepath."""

    default_content_type = 'application/json'

    def __init__(self, catalog, elem):
        Api.__init__(self, catalog)
        self.Entity = Entity(catalog, elem)
        self.apath = None
        self.http_vary.add('accept')

    def append(self, elem):
        self.Entity.append(elem)

    def set_projection(self, attributes):
        self.apath = ermpath.AttributePath(self.Entity.epath, _preprocess_attributes(self.Entity.epath, attributes))
        
    def GET(self, uri):
        """Perform HTTP GET of attributes.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn, cur):
            self.enforce_content_read(cur, uri)
            self.set_http_etag( self.apath.epath.get_data_version(cur) )
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return None
            self.apath.add_sort(self.sort)
            return self.apath.get(conn, cur, content_type=content_type, limit=limit)

        def post_commit(lines):
            self.emit_headers()
            if lines is None:
                return
            web.header('Content-Type', content_type)
            web.ctx.ermrest_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

    def DELETE(self, uri):
        """Perform HTTP DELETE of entity attribute.
        """
        def body(conn, cur):
            self.enforce_content_write(cur, uri)
            self.apath.delete(conn, cur)

        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)

class AttributeGroup (Api):
    """A specific group set by entity path, group keys, and group attributes."""

    default_content_type = 'application/json'

    def __init__(self, catalog, elem):
        Api.__init__(self, catalog)
        self.Entity = Entity(catalog, elem)
        self.agpath = None
        self.http_vary.add('accept')

    def append(self, elem):
        self.Entity.append(elem)

    def set_projection(self, groupkeys, attributes):
        self.agpath = ermpath.AttributeGroupPath(
            self.Entity.epath,
            _preprocess_attributes(self.Entity.epath, groupkeys),
            _preprocess_attributes(self.Entity.epath, attributes)
        )
    
    def GET(self, uri):
        """Perform HTTP GET of attribute groups.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn, cur):
            self.enforce_content_read(cur, uri)
            self.set_http_etag( self.agpath.epath.get_data_version(cur) )
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return None
            self.agpath.add_sort(self.sort)
            return self.agpath.get(conn, cur, content_type=content_type, limit=limit)

        def post_commit(lines):
            self.emit_headers()
            if lines is None:
                return
            web.header('Content-Type', content_type)
            web.ctx.ermrest_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

    def PUT(self, uri, post_method=False):
        """Perform HTTP PUT of attribute groups.
        """
        try:
            in_content_type = web.ctx.env['CONTENT_TYPE'].lower()
            in_content_type = in_content_type.split(";", 1)[0].strip()
        except:
            in_content_type = self.default_content_type

        content_type = negotiated_content_type(default=in_content_type)

        input_data = cStringIO.StringIO(web.ctx.env['wsgi.input'].read())
        
        def body(conn, cur):
            input_data.seek(0) # rewinds buffer, in case of retry
            self.enforce_content_write(cur, uri)
            return self.agpath.put(
                conn,
                cur,
                input_data, 
                in_content_type=in_content_type
            )

        def post_commit(lines):
            web.header('Content-Type', content_type)
            web.ctx.ermrest_request_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)


class Aggregate (Api):
    """A specific aggregate tuple."""

    default_content_type = 'application/json'

    def __init__(self, catalog, elem):
        Api.__init__(self, catalog)
        self.Entity = Entity(catalog, elem)
        self.agpath = None
        self.http_vary.add('accept')

    def append(self, elem):
        self.Entity.append(elem)

    def set_projection(self, attributes):
        self.agpath = ermpath.AggregatePath(self.Entity.epath, _preprocess_attributes(self.Entity.epath, attributes))
    
    def GET(self, uri):
        """Perform HTTP GET of attribute groups.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn, cur):
            self.enforce_content_read(cur, uri)
            self.set_http_etag( self.agpath.epath.get_data_version(cur) )
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return None
            self.agpath.add_sort(self.sort)
            return self.agpath.get(conn, cur, content_type=content_type, limit=limit)

        def post_commit(lines):
            self.emit_headers()
            if lines is None:
                return
            web.header('Content-Type', content_type)
            web.ctx.ermrest_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

