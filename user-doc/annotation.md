# Model Annotation

This document defines a set of annotations we suggest may be useful in
combination with ERMrest. We define a set of _annotation keys_, any
associated JSON _annotation values_, and their semantics. Communities
may use these conventions to modify their interpretation of ERMrest
catalog content.

These annotations do not affect the behavior of the ERMrest service
itself but merely inform clients about intended use beyond that
captured in the entity-relationship model. Further, as described in
the [REST API docs](../api-doc/index.md), the annotation system is
openly extensible so communities MAY use other annotation keys not
described here; in those cases, the community SHOULD publish similar
documentation on their use and interpretation.

## Notation and Usage

Each annotation key is defined in a section of this document and shown
as a literal string.  We prepend a date in each key name and promise
not to modify the semantics of an existing annotation key, once
published to GitHub. We may publish typographical or other small
textual clarifications, but if we need to change the proposed
semantics we will define a new key with a different date and/or key
text. We will follow the date stamp conventions from
[RFC 4151](http://www.faqs.org/rfcs/rfc4151.html) which allow for
abbreviated ISO dates such as `2015`, `2015-01`, and `2015-01-01`.

### Example to Set Annotation

This example sets the
[2015 Display](#2015-display) annotation:

    PUT /ermrest/catalog/1/schema/MainContent/annotation/tag%3Amisd.isi.edu%2C2015%3Adisplay HTTP/1.1
    Host: www.example.com
    Content-Type: application/json

    {"name": "Main Content"}

TBD changes to propose for ERMrest:

1. Allow non-escaped characters in the annotation key since it is the final field of the URL and does not have a parsing ambiguity?
2. Allow an empty (0 byte) request body to represent the same thing as JSON `null`?

## Annotations

Some annotations are supported on multiple types of model element, so
here is a quick matrix to locate them.

| Annotation | Schema | Table | Column | Key | FKR | Summary |
|------------|--------|-------|--------|-----|-----|---------|
| [2015 Display](#2015-display) | X | X | X | - | - | Display options |
| [2015 Vocabulary](#2015-vocabulary) | - | X | - | - | - | Table as a vocabulary list |
| [2016 Abstracts Table](#2016-abstracts-table) | - | X | - | _ | _ | Table abstracts another table |
| [2016 Column Display](#2016-column-display) | - | - | X | - | - | Column-specific display options |
| [2016 Foreign Key](#2016-foreign-key) | - | - | - | - | X | Foreign key augmentation |
| [2016 Generated](#2016-generated) | - | - | X | - | - | Generated column element |
| [2016 Ignore](#2016-ignore) | X | X | - | - | - | Ignore model element |
| [2016 Immutable](#2016-immutable) | - | - | X | - | - | Immutable column element |
| [2016 Record Link](#2016-record-link) | X | X | - | - | - | Intra-Chaise record-level app links |
| [2016 Table Display](#2016-table-display) | X | X | - | - | - | Table-specific display options |
| [2016 Visible Columns](#2016-visible-columns) | - | X | - | - | - | Column visibility and presentation order |
| [2016 Visible Foreign Keys](#2016-visible-foreign-keys) | - | X | - | - | - | Foreign key visibility and presentation order |

For brevity, the annotation keys are listed above by their section
name within this documentation. The actual key URI follows the form
`tag:misd.isi.edu,` _date_ `:` _key_ where the _key_ part is
lower-cased with hyphens replacing whitespace. For example, the 
`2015 Display` annotation key URI is actually
`tag:misd.isi.edu,2015:display`.

### 2015 Display

`tag:misd.isi.edu,2015:display`

This key is allowed on any number of schemas, tables, and
columns. This annotation indicates display options for the indicated
element and its nested model elements.

Supported JSON payload patterns:

- `{`... `"name":` _name_ ...`}`: The _name_ to use in place of the model element's original name.
- `{`... `"name_style":` `{` `"underline_space"`: _uspace_ `,` `"title_case":` _tcase_ `}` ...`}`: Element name conversion instructions.
- `{`... `"show_nulls":` `{` _ncontext_ `:` _nshow_ `,` ... `}`: How to display NULL data values.

Supported JSON _uspace_ patterns:

- `true`: Convert underline characters (`_`) into space characters in model element names.
- `false`: Leave underline characters unmodified (this is also the default if the setting is completely absent).

Supported JSON _tcase_ patterns:

- `true`: Convert element names to "title case" meaning the first character of each word is capitalized and the rest are lower cased regardless of model element name casing. Word separators include white-space, hyphen, and underline characters.
- `false`: Leave character casing unmodified (this is also the default if the setting is completely absent).

Supported JSON _nshow_ patterns:

- `true` (or `""`): Show NULL values as an empty field.
- `"` _marker_ `"` (a quoted string literal): For any string literal _marker_, display the marker text value in place of NULLs.
- `false`: Completely eliminate the field if feasible in the presentation.

Supported JSON _ncontext_ patterns:

- `entry`: Use _nshow_ instruction when displaying NULL values for data-entry.
  - `entry/create`: Use _nshow_ instruction when displaying NULL values for creation (such as in a drop-down list?).
  - `entry/edit`: Use _nshow_ instruction when displaying existing NULL values to be edited.
- `filter`: Use _nshow_ instruction when displaying NULL values in filtering controls.
- `compact`: Use _nshow_ instruction when presenting data in compact, tabular formats.
- `detailed`: Use _nshow_ instruction when presenting data in detailed, entity-level formats.
- `"*"`: Use _nshow_ instruction as the default for any context not specifically configured in this annotation.

#### 2015 Display Settings Hierarchy

- The `"name"` setting applies *only* to the model element which is annotated.
- The `"name_style"` setting applies to the annotated model element and is also the default for any nested element.
- The `"show_nulls"` settings applies to the annotated model element and is also the default for any nested element.
  - The annotation is allowed on schemas in order to set the default for all tables in the schema.
  - Each _ncontext_ `:` _nshow_ instruction overrides the inherited instruction for the same _ncontext_ while still deferring to the inherited annotation for any unspecified _ncontext_. The `"*"` wildcard _ncontext_ allows masking of any inherited instruction.
  - A global default is assumed: `{`... `"show_nulls": { "detailed": false, "*": true` ... `}`

This annotation provides an override guidance for Chaise applications using a hierarchical scoping mode:

1. Column-level name
2. Column-level name_style. 
3. Table-level name_style. 
4. Schema-level name_style. 

Note: 
- An explicit setting of `null` will turn *off* inheritence and restore default behavior for that modele element and any of its nested elements.
- The name_style has to be derived separately for each field e.g. one can set `underline_space=true` at the schema-level and doesn't have to set this again.   

### 2015 Vocabulary

`tag:misd.isi.edu,2015:vocabulary`

This key is allowed on any number of tables in the model, where the
table contains at least one key comprised of a single textual
column. A vocabulary table is one where each row represents a term or
concept in a controlled vocabulary.

Supported JSON payload patterns:

- `null` or `{}`: Default heuristics apply.
- `{`... `"uri":` _uri_ ...`}`: The _uri_ indicates the global identifier of the controlled vocabulary. The _uri_ MAY be a resolvable URL.
- `{`... `"term":` _column_ ...`}`: The named _column_ stores the preferred textual representation of the term. The referenced column MUST comprise a single-column key for the table.
- `{`... `"id":` _column_ ...`}`: The named _column_ stores the preferred compact identifier for the term, which MAY be textual or numeric. The referenced column MUST comprise a single-column key for the table.
- `{`... `"internal":` [_column_, ...] ...`}`: The one or more named _columns_ store internal identifiers for the term, used for efficient normalized storage in the database but not meaningful to typical users. The referenced columns MUST each comprise a single-column key for the table.
- `{`... `"description":` _column_ ...`}`: The named _column_ stores a longer textual representation of the term or concept. The referenced column SHOULD comprise a single-column key for the table.

#### Heuristics

1. In the absence of an `internal` assertion, assume all keys are potentially meaningful to users.
2. In the absence of a `term` assertion
  - Try to find a single-column key named `term`
  - Try to find a single-column key named `name`
  - If no term column is found table SHOULD NOT be interpreted as a vocabulary.
3. In the absence of an `id` assertion
  - Try to find a column named `id`
  - Try to find an unambiguous single-column numeric key
  - If no `id` column is found, use the term column as the preferred compact identifier.
4. In the absence of a `description` assertion
  - Try to find a column named `description`
  - If no description column is found, proceed as if there is no description or use some other detailed or composite view of the table rows as a long-form presentation.

In the preceding, an "unambiguous" key means that there is only one
key matching the specified type and column count.

The preferred compact identifier is more often used in dense table
representations, technical search, portable data interchange, or
expert user scenarios, while the preferred textual representation is
often used in prose, long-form presentations, tool tips, or other
scenarios where a user may need more natural language understanding of
the concept.

### 2016 Ignore

`tag:isrd.isi.edu,2016:ignore`

This key is allowed on any number of the following model elements:

- Schema
- Table

This key was previously specified for these model elements but such use is deprecated:

- Column (use [2016 Visible Columns](#2016-visible-columns) instead)
- Foreign Key (use [2016 Visible Foreign Keys](#2016-visible-foreign-keys) instead)

This annotation indicates that the annotated model element should be ignored in typical model-driven user interfaces, with the presentation behaving as if the model element were not present. The JSON payload contextualizes the user interface mode or modes which should ignore the model element.

Supported JSON payload patterns:
- `null` or `true`: Ignore in any presentation context. `null` is equivalent to `tag:misd.isi.edu,2015:hidden` for backward-compatibility.
- `[]` or `false`: Do **not** ignore in any presentation context.
- `[` _context_ `,` ... `]`: Ignore **only** in specific listed contexts drawn from the following list, otherwise including the model element as per default heuristics:
  - `entry`: Avoid prompting of the user for input to whole schemas or whole tables while obtaining user input.
    - `entry/edit`: A sub-context of `entry` that only applies to editing existing resources.
	- `entry/create`: A sub-context of `entry` that only applies to creating new resources.
  - `filter`: Avoid offering filtering options on whole schemas or whole tables.
  - `compact`: Avoid presenting data related to whole schemas or whole tables when presenting data in compact, tabular formats.
  - `detailed`: Avoid presenting data related to whole schemas or whole tables when presenting data in detailed, entity-level formats.

This annotation provides an override guidance for Chaise applications
using a hierarchical scoping mode:

1. Hard-coded default behavior in Chaise codebase.
2. Server-level configuration in `chaise-config.js` on web server overrides hard-coded default.
3. Schema-level annotation overrides server-level or codebase behaviors.
4. Table-level annotation overrides schema-level, server-level, or codebase behaviors.
5. Annotations on the column or foreign key reference levels override table-level, schema-level, server-level, or codebase behaviors.


### 2016 Record Link

`tag:isrd.isi.edu,2016:recordlink`

This key is allowed on any number of schemas or tables in the
model. It is used to indicate which record-level application in the
Chaise suite should be linked from rows in a search or other row-set
presentation.

Supported JSON payload patterns:

- `{ "mode":` _mode_ `, "resource":` _relpath_ `}`: Link to _relpath_ app resource, forming a URL using linking _mode_.
  - The `mode` _mode_ SHOULD be the following fixed constant (unless additional modes are defined in a future revision):
    - `"tag:isrd.isi.edu,2016:recordlink/fragmentfilter"`: form an application link as, e.g., `/chaise/` _relpath_ `?` _catalog_ `/` _schema_ `:` _table_ `/` _filter_ where _filter_ is a simple ERMrest predicate such as `columnname:eq:value`.
  - The `resource` _relpath_ SHOULD be a relative path to one of the supported Chaise record-level applications:
    - `"record/"`
    - `"viewer/"`

This annotation provides an override guidance for Chaise applications
using a hierarchical scoping mode:

1. Hard-coded default behavior in Chaise codebase.
2. Server-level configuration in `chaise-config.js` on web server overrides hard-coded default.
3. Schema-level annotation overrides server-level or codebase behaviors.
4. Table-level annotation overrides schema-level, server-level, or codebase behaviors.

### 2016 Immutable

`tag:isrd.isi.edu,2016:immutable`

This key indicates that the values for a given column may not be mutated
(changed) once set. This key is allowed on any number of columns. There is no
content for this key.

### 2016 Generated

`tag:isrd.isi.edu,2016:generated`

This key indicates that the values for a given column will be generated by
the system. This key is allowed on any number of columns. There is no content
for this key.

### Pattern Expansion

When deriving a field value from a _pattern_, the _pattern_ MAY contain markers for substring replacements of the form `{column name}` where `column name` MUST reference a column in the table. Any particular column name MAY be referenced and expanded zero or more times in the same _pattern_.

For example, a _table_ may have a [`tag:misd.isi.edu,2015:url`](#2015-url) annotation containing the following payload:

```
{
    "pattern": "https://www.example.org/collections/{collection}/media/{object}",
    "presentation": "embed"
}
```

A web user agent that consumes this annotation and the related table data would likely embed the following `<iframe>` tag for each entity:

```
<iframe src="https://www.example.org/collections/123/media/XYZ"></iframe>
```

### 2016 Visible Columns

`tag:isrd.isi.edu,2016:visible-columns`

This key indicates that the presentation order and visibility for
columns in a table, overriding the defined table structure.

Supported JSON payload pattern:

- `{` ... _context_ `:` _columnlist_ `,` ... `}`: A separate _columnlist_ can be specified for any number of _context_ names.
- `{` ... _context1_ `:` _context2_ `,` ... `}`: Configure _context1_ to use the same _columnlist_ configured for _context2_.

For presentation contexts which are not listed in the annotation, or when the annotation is entirely absent, all available columns SHOULD be presented in their defined order unless the application has guidance from other sources.

Supported _context_ names:

- `"entry"`: Any data-entry presentation context, i.e. when prompting the user for input column values.
  - `"entry/edit"`: A sub-context of `entry` that only applies to editing existing resources.
  - `"entry/create"`: A sub-context of `entry` that only applies to creating new resources.
- `"record"`: Any detailed record-level presentation context.
- `"filter"`: Any data-filtering control context, i.e. when prompting the user for column constraints or facets.
- `"compact"`: Any compact, tabular presentation of data from multiple entities.
- `"*"`: A default to apply for any context not matched by a more specific context name.

Supported _columnlist_ patterns:

- `[` ... _colentry_ `,` ... `]`: Present content corresponding to each _colentry_, in the order specified in the list. Ignore listed _colentry_ values that do not correspond to content from the table. Do not present table columns that are not specified in the list.

Supported _columnentry_ patterns:

- _columnname_: A string literal _columnname_ identifies a constituent column of the table. The value of the column SHOULD be presented, possibly with representation guided by other annotations or heuristics.
- `[` _schemaname_ `,` _constraintname_ `]`: A two-element list of string literal _schemaname_ and _constraintname_ identifies a constituent foreign key of the table. The value of the external entity referenced by the foreign key SHOULD be presented, possibly with representation guided by other annotations or heuristics.

### 2016 Foreign Key

`tag:isrd.isi.edu,2016:foreign-key`

This key allows augmentation of a foreign key reference constraint
with additional presentation information.

Supported JSON payload patterns:

- `{` ... `"from_name":` _fname_ ... `}`: The _fname_ string is a preferred name for the set of entities containing foreign key references described by this constraint.
- `{` ... `"to_name":` _tname_ ... `}`: The _tname_ string is a preferred name for the set of entities containing keys described by this constraint.

Heuristics (use first applicable rule):

1. A set of "related entities" make foreign key reference to a presentation context:
  - The _fname_ is a preferred name for the related entity set.
  - The name of the table containing the related entities may be an appropriate name for the set, particularly if the table has no other relationship to the context.
  - The name of the table can be composed with other contextual information, e.g. "Tablename having columnname = value".
2. To name a set of "related entities" linked to a presentation context by an association table:
  - The _tname_ of the foreign key from association table to related entities is a preferred name for the related entity set.
  - The name of the table containing the related entities may be an appropriate name for the set, particularly if the table has no other relationship to the context.

### 2016 Column Display

`tag:isrd.isi.edu,2016:column-display`

This key allows specification of column data presentation options at the column level of the model.

Supported JSON payload patterns:

- `{` ... _context_ `:` `{` _option_ ... `}` ... `}`: Apply each _option_ to the presentation of column values in the given _context_.
- `{` ... _context1_ `:` _context2_ ... `}`: Short-hand to allow _context1_ to use the same options configured for _context2_.

Supported _context_ names:

- `"entry"`: Any data-entry presentation context, i.e. when prompting the user for input column values.
  - `"entry/edit"`: A sub-context of `entry` that only applies to editing existing resources.
  - `"entry/create"`: A sub-context of `entry` that only applies to creating new resources.
- `"record"`: Any detailed record-level presentation context.
- `"filter"`: Any data-filtering control context, i.e. when prompting the user for column constraints or facets.
- `"compact"`: Any compact, tabular presentation of data from multiple entities.
- `"*"`: A default to apply for any context not matched by a more specific context name.

If more than one _context_ name in the annotation payload matches, the _options_ should be combined in the following order (first occurrence wins):

1. Prefer _option_ set in matching contexts with exact matching context name.
2. Prefer _option_ set in matching contexts with longest matching prefix, e.g. an option for `entry` can match application context `entry/edit` or `entry/create`.
3. Use default _option_ set in context `*`.

Supported _option_ syntax:

- `"pre_format"`: _format_: The column value SHOULD be pre-formatted by evaluating the _format_ string with the raw column value as its sole argument. The exact format string dialect is TDB but means to align with POSIX format strings e.g. `%d` to format a decimal number.
- `"markdown_pattern":` _pattern_: The visual presentation of the column SHOULD be computed by performing [Pattern Expansion](#pattern-expansion) on _pattern_ to obtain a markdown-formatted text value which MAY be rendered using a markdown-aware renderer.

All `pre_format` options for all columns in the table SHOULD be evaluated **prior** to any `markdown_pattern`, thus allowing raw data values to be adjusted by each column's _format_ option before they are substituted into any column's _pattern_.

### 2016 Table Display

`tag:isrd.isi.edu,2016:table-display`

This key allows specification of table presentation options at the table or schema level of the model.

- `{` ... _context_ `:` `{` _option_ ... `}` ... `}`: Apply each _option_ to the presentation of table content in the given _context_.
- `{` ... _context1_ `:` _context2_ ... `}`: Short-hand to allow _context1_ to use the same options configured for _context2_.

Supported _context_ names:

- `"name"`: Any abbreviated title-like presentation context.
- `"record"`: Any detailed record-level presentation context.
- `"filter"`: Any data-filtering control context, i.e. when prompting the user for column constraints or facets.
- `"compact"`: Any compact, tabular presentation of data from multiple entities.
- `"*"`: A default to apply for any context not matched by a more specific context name.

Supported JSON _option_ payload patterns:

- `"row_order":` `[` _sortkey_ ... `]`: The list of one or more _sortkey_ defines the preferred or default order to present rows from a table. The ordered list of sort keys starts with a primary sort and optionally continues with secondary, tertiary, etc. sort keys.
- `"row_markdown_pattern":` _rowpattern_: Render the row by composing a markdown representation only when `row_markdown_pattern` is non-null.
  - Expand _rowpattern_ to obtain a markdown representation of each row via [Pattern Expansion](#pattern-expansion). The pattern has access to column values **after** any processing implied by [2016 Column Display](#2016-column-display).
- `"separator_markdown":` _separator_: Insert _separator_ markdown text between each expanded _rowpattern_ when presenting row sets. (Default new-line `"\n"`.)
  - Ignore if `"row_markdown_pattern"` is not also configured.
- `"prefix_markdown":` _prefix_: Insert _prefix_ markdown before the first _rowpattern_ expansion when presenting row sets. (Default empty string `""`.)
  - Ignore if `"row_markdown_pattern"` is not also configured.
- `"suffix_markdown":` _suffix_: Insert _suffix_ markdown after the last _rowpattern_ expansion when presenting row sets. (Default empty string `""`.)
  - Ignore if `"row_markdown_pattern"` is not also configured.
- `"module":` _module_: Activate _module_ to present the entity set. The string literal _module_ name SHOULD be one that Chaise associates with a table-presentation plug-in.
- `"module_attribute_path":` _pathsuffix_: Configure the data source for activated _module_. Ignore if _module_ is not configured or not understood.
  - If _pathsuffix_ is omitted, use the ERMrest `/entity/` API and a data path denoting the desired set of entities.
  - If _pathsuffix_ is specified, use the ERMrest `/attribute/` API and append _pathsuffix_ to a data path denoting the desired set of entities and which binds `S` as the table alias for this entire entity set.
    - The provided _pathsuffix_ MUST provide the appropriate projection-list to form a valid `/attribute/` API URI.
	- The _pathsuffix_ MAY join additional tables to the path and MAY project from these tables as well as the table bound to the `S` table alias.
	- The _pathsuffix_ SHOULD reset the path context to `$S` if it has joined other tables.
	
It is not meaningful to use both `row_markdown_pattern` and `module` in for the same _context_. If both are specified, it is RECOMMENDED that the application prefer the `module` configuration and ignore the markdown instructions.

Supported JSON _sortkey_ patterns:

- `{ "column":` _columnname_ `, "descending": true }`: Sort according to the values in the _columnname_ column in descending order. This is equivalent to the ERMrest sort specifier `@sort(` _columnname_ `::desc::` `)`.
- `{ "column":` _columnname_ `, "descending": false }`: Sort according to the values in the _columnname_ column in ascending order. This is equivalent to the ERMrest sort specifier `@sort(` _columnname_ `)`.
- `{ "column":` _columnname_ `}`: If omitted, the `"descending"` field defaults to `false` as per above.
- `"` _columnname_ `"`: A bare _columnname_ is a short-hand for `{ "column":` _columnname_ `}`.

#### 2016 Table Display Settings Hierarchy

The table display settings apply only to tables, but MAY be annotated at the schema level to set a schema-wide default, if appropriate in a particular model. Any table-level specification of these settings will override the behavior for that table. These settings on other model elements are meaningless and ignored.

For hierarchically inheritable settings, an explicit setting of `null` will turn *off* inheritence and restore default behavior for that model element and any of its nested elements.

### 2016 Visible Foreign Keys

`tag:isrd.isi.edu,2016:visible-foreign-keys`

This key indicates that the presentation order and visibility for
foreign keys referencing a table, useful when presenting "related entities".

Supported JSON payload pattern:

- `{` ... _context_ `:` _fkeylist_ `,` ... `}`: A separate _fkeylist_ can be specified for any number of _context_ names.
- `{` ... _context1_ `:` _context2_ ... `}`: Short-hand to allow _context1_ to use the same fkeylist configured for _context2_.

For presentation contexts which are not listed in the annotation, or when the annotation is entirely absent, all available foreign keys SHOULD be presented unless the application has guidance from other sources.

Supported _context_ names:

- `entry`: Any data-entry presentation context, i.e. when prompting the user for input column values.
  - `entry/edit`: A sub-context of `entry` that only applies to editing existing resources.
  - `entry/create`: A sub-context of `entry` that only applies to creating new resources.
- `filter`: Any data-filtering control context, i.e. when prompting the user for column constraints or facets.
- `compact`: Any compact, tabular presentation of data from multiple entities.

Supported _keylist_ patterns:

- `[` `[` _schema name_`,` _constraint name_ `]` `,` ... `]`: Present foreign keys with matching _schema name_ and _constraint name_, in the order specified in the list. Ignore constraint names that do not correspond to foreign keys in the catalog. Do not present foreign keys that are not mentioned in the list. These 2-element lists use the same format as each element in the `names` property of foreign keys in the JSON model introspection output of ERMrest.

### 2016 Abstracts Table

`tag:isrd.isi.edu,2016:abstracts-table`

This key indicates that the annotated table _abstracts_ another
table. This means that they both represent the same _entity set_ but
the abstraction has modified the representation of each entity in some
way.

Supported JSON payload patterns:

- `{` ... `"schema" :` _sname_, `"table" :` _tname_ ... `}`: The table identified by _sname_:_tname_ is the base storage table being abstracted by the table bearing this annotation.
- `{` ... `"contexts" : [` _context_ `,` ... `]` ... `}`: The abstraction is preferred in the listed application context(s).

A table which abstracts another table _SHOULD_ have a non-null (primary) key which is also a foreign key to the table it abstracts. Otherwise, a consuming application would not know how to navigate from one abstracted representation of an entity to another representation from the base storage tables.

Supported _context_ names:

- `filter`: Any data-filtering control context, i.e. when prompting the user for column constraints or facets.
- `compact`: Any compact, tabular presentation of data from multiple entities.
- `detailed`: Any read-only, entity-level presentation.

It is assumed that any application context that is performing mutation (record creation, deletion, or editing) MUST use a base entity storage table that is not an abstraction over another table. However, the use of the `detailed` context MAY offer an abstraction that augments the presentation of an existing record. An application offering mutation options while displaying an existing entity record might then present the data from the `detailed` abstraction but only offer editing or data-entry controls on the fields available from the base storage table.
