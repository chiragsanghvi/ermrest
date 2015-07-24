
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

"""ERMREST data path support

The data path is the core ERM-aware mechanism for searching,
navigating, and manipulating data in an ERMREST catalog.

"""
import psycopg2
import urllib
import csv
import web

from ..util import sql_identifier, sql_literal
from .. import exception

def _default_link_table2table(left, right):
    """Find default reference link between left and right tables.

       Returns (keyref, refop).

       Raises exception.ConflictModel if no default can be found.
    """
    if left == right:
        raise exception.ConflictModel('Ambiguous self-link for table %s' % left)

    links = []

    # look for right-to-left references
    for pk in left.uniques.values():
        if right in pk.table_references:
            links.extend([
                    (ref, '@=')
                    for ref in pk.table_references[right]
                    ])

    # look for left-to-right references
    for fk in left.fkeys.values():
        if right in fk.table_references:
            links.extend([
                    (ref, '=@')
                    for ref in fk.table_references[right]
                    ])

    if len(links) == 0:
        raise exception.ConflictModel('No link found between tables %s and %s' % (left, right))
    elif len(links) == 1:
        return links[0]
    else:
        raise exception.ConflictModel('Ambiguous links found between tables %s and %s' % (left, right))

class Name (object):
    """Represent a qualified or unqualified name in an ERMREST URL.

    """
    def __init__(self, nameparts=None):
        """Initialize a zero-element name container.
        """
        self.nameparts = nameparts and list(nameparts) or []
        self.alias = None

    def set_alias(self, alias):
        self.alias = alias
        return self

    def __str__(self):
        return ':'.join(map(urllib.quote, self.nameparts))
    
    def __repr__(self):
        return '<ermrest.url.ast.Name %s>' % str(self)

    def __len__(self):
        return len(self.nameparts)

    def __iter__(self):
        return iter(self.nameparts)

    def with_suffix(self, namepart):
        """Append a namepart to a qualifying prefix, returning full name.

           This method mutates the name and returns it as a
           convenience for composing more calls.
        """
        self.nameparts.append(namepart)
        return self
        
    def resolve_column(self, model, epath, table=None):
        """Resolve self against a specific database model and epath context.

           Returns (column, base) where base is one of:

            -- a left table alias string if column is relative to alias
            -- epath if column is relative to epath or table arg
            -- None if column is relative to model
        
           The name must be resolved in this preferred order:

             1. a relative 'n0' must be a column in the current epath
                table type or the provided table arg if not None

             2. a relative '*' may be a freetext virtual column
                on the current epath table

             3. a relative 'n0:n1' may be a column in alias n0 of
                current epath

             4. a relative 'n0:*' may be a freetext virtual column
                in alias n0 of current epath

             5. a relative 'n0:n1' may be a column in a table in the
                model

             6. any 'n0:n1:n2' must be a column in the model

           Raises exception.ConflictModel on failed resolution.
        """
        ptable = epath.current_entity_table()

        if table is None:
            table = ptable
        
        if len(self.nameparts) == 3:
            n0, n1, n2 = self.nameparts
            table = model.lookup_table(n0, n1)
            if n2 in table.columns:
                return (table.columns[n2], None)
            else:
                raise exception.ConflictModel('Column %s does not exist in table %s.' % (n2, str(table)))
        
        else:
            if len(self.nameparts) == 1:
                if self.nameparts[0] in table.columns:
                    return (table.columns[self.nameparts[0]], epath)
                elif self.nameparts[0] == '*':
                    return (ptable.freetext_column(), epath)
                else:
                    raise exception.ConflictModel('Column %s does not exist in table %s.' % (self.nameparts[0], str(table)))

            elif len(self.nameparts) == 2:
                n0, n1 = self.nameparts
                if n0 in epath.aliases:
                    if n1 in epath[n0].table.columns:
                        return (epath[n0].table.columns[n1], n0)
                    elif self.nameparts[1] == '*':
                        return (epath[n0].table.freetext_column(), n0)
                    else:
                        raise exception.ConflictModel('Column %s does not exist in table %s (alias %s).' % (n1, epath[n0].table, n0))

                table = model.lookup_table(None, n0)
                if n1 not in table.columns:
                    raise exception.ConflictModel('Column %s does not exist in table %s.' % (n1, table.name))

                return (table.columns[n1], None)

        raise exception.BadSyntax('Name %s is not a valid syntax for columns.' % self)

    def resolve_context(self, epath):
        """Resolve self against a specific entity path for which we must be an alias, returning alias string."""
        if len(self.nameparts) > 1:
            raise exception.BadSyntax('Context name %s is not a valid syntax for an entity alias.' % self)
        try:
            return epath[str(self.nameparts[0])].alias
        except KeyError:
            raise exception.BadData('Context name %s is not a bound alias in entity path.' % self)

    def resolve_link(self, model, epath):
        """Resolve self against a specific database model and epath context.

           Returns (keyref, refop, lalias) as resolved key reference
           configuration.
        
           A name 'n0' must be an unambiguous table in the model

           A name 'n0:n1' must be a table in the model

           The named table must have an unambiguous implicit reference
           to the epath context.

           Raises exception.ConflictModel on failed resolution.
        """
        ptable = epath.current_entity_table()
        
        if len(self.nameparts) == 1:
            name = self.nameparts[0]
            table = self.resolve_table(model)
            keyref, refop = _default_link_table2table(ptable, table)
            return keyref, refop, None

        elif len(self.nameparts) == 2:
            n0, n1 = self.nameparts

            table = model.lookup_table(n0, n1)
            keyref, refop = _default_link_table2table(ptable, table)
            return keyref, refop, None

        raise exception.BadSyntax('Name %s is not a valid syntax for a table name.' % self)

    def resolve_table(self, model):
        """Resolve self as table name.
        
           Qualified names 'n0:n1' can only be resolved from the model
           as schema:table.  Bare names 'n0' can be resolved as table
           if that is unambiguous across all schemas in the model.

           Raises exception.ConflictModel on failed resolution.
        """
        if len(self.nameparts) == 2:
            sname, tname = self.nameparts
            return model.lookup_table(sname, tname)
        elif len(self.nameparts) == 1:
            tname = self.nameparts[0]
            return model.lookup_table(None, tname)

        raise exception.BadSyntax('Name %s is not a valid syntax for a table name.' % self)
            
    def validate(self, epath):
        """Validate name in epath context, raising exception on problems.

           Name must be a column of path's current entity type 
           or alias-qualified column of ancestor path entity type.
        """
        table = epath.current_entity_table()
        col, base = self.resolve_column(epath._model, epath)
        if base == epath:
            return col, epath._path[epath.current_entity_position()]
        elif base in epath.aliases:
            return col, epath._path[epath.aliases[base]]

        raise exception.ConflictModel('Referenced column %s not bound in entity path.' % (col.table))

    def sql_column(self, epath, elem):
        """Generate SQL column reference for name in epath elem context.

           TODO: generalize to ancestor references later.
        """
        return 't%d.%s' % (
            elem.pos,
            sql_identifier(self.nameparts[-1])
            )

    def sql_literal(self, etype):
        if len(self.nameparts) == 1:
            return Value(self.nameparts[0]).sql_literal(etype)
        else:
            raise exception.BadSyntax('Names such as "%s" not supported in filter expressions.' % self)
        
    def validate_attribute_update(self):
        """Return icolname for valid input column reference.
           
        """
        if len(self.nameparts) == 1:
            return self.nameparts[0]
        else:
            raise exception.BadSyntax('Name "%s" is not a valid input column reference.' % self)

