
# Chado Vocabulary Patterns

This page is to explore some possible use-case patterns for using
Chado schema for controlled vocabularies.

## Assumptions and conventions

1. We want to load ontologies easily, so being consistent with Chado is probably helpful.
2. We want to separate ontology/vocabulary preparation from normal data management operations
  - Vocabularies and terms are defined *before* use in data tables
  - Restricted domain tables are used to present subsets of ontologies for use in data columns
  - Data serialization should not depend on order vocabularies are loaded
3. We will use the dbxref concept specifically with _DB_ `:` _ACCESSION_ `:` _VERSION_ textual formatted indentifiers as keys and foreign keys in vocabulary storage columns, e.g. `OBO_REL:is_a:`.

## Chado-derived core tables

Assume a basic ontology storage area similar to
[Chado CV Module](http://gmod.org/wiki/Chado_CV_Module).  Here, we
only focus on the few tables that would affect normal data
management. Additional tables may exist for vocabulary management but
once vocabularies are populated, only the following tables matter for
normal data I/O and query.

### cvterm

The `cvterm` table enumerates all available terms.

```
CREATE TABLE cvterm (
  cvterm_id serial PRIMARY KEY,
  dbxref text UNIQUE NOT NULL,
  cvname text NOT NULL,
  name text NOT NULL,
  definition text,
  is_obsolete boolean NOT NULL,
  is_relationshiptype boolean NOT NULL,
  UNIQUE (cvname, name, is_obsolete)
);
```

We simplify the dbxref model:

1. Don't need/want serial IDs except for efficient internal mappings
2. Want direct denormalized access to dbxref

### cvtermpath

The `cvtermpath` table stores transitive closures of term-to-term relationship graphs.

```
CREATE TABLE cvtermpath (
  type_id integer NOT NULL REFERENCES cvterm (cvterm_id),
  subject_id integer NOT NULL REFERENCES cvterm (cvterm_id),
  object_id integer NOT NULL REFERENCES cvterm (cvterm_id),
  pathdistance integer NOT NULL,
  UNIQUE (type_id, subject_id, object_id)
);
```

We constrain the path table:

1. Don't allow NULL `type_id` which is a closure over multiple relationships
2. Don't store multiple rows for same subject, relationship, object. Store *minimum* path distance.

## Domain tables

We can have any number of domain tables to enumerate a subset of
controlled vocabulary terms.

```
CREATE TABLE mydomain1 (
  dbxref text PRIMARY KEY REFERENCES cvterm (dbxref)
);
```

## Data tables using controlled terms

We can use controlled vocabularies for any number of data columns by
configuring a foreign key constraint to a domain table.

```
CREATE TABLE mydata (
   ...
   myconcept text REFERENCES mydomain1 (dbxref),
   ...
);
```

## Heuristics and idioms

### Basic data access

Naive access to data tables can completely ignore the connections to a
vocabulary and just consume the stored data column as explicit dbxref
strings.

### Data integrity and basic value enumeration

Any consumer can introspect the data table and understand the foreign
key constraint to see which dbxref values are allows in a data
column. The database will enforce the foreign key integrity to prevent
values from being added to a data column outside the configured domain
term set.

### Prettier term display

Any consumer can recognize the foreign key chain, through domain
table, to the `cvterm` table to understand how to retrieve name or
definition information from a dbxref value.

Options:

1. Hard-code detection of `cvterm` table name in some specific schema?
2. Rely on schema annotation to mark the `cvterm` table as a vocabulary?
3. Do duck-type signature detection to recognize the structure of `cvterm` table?

### Semantic search via transitive closures

Any consumer can recognize the foreign key chain, through domain
table, to the `cvterm` table and the presence of the `cvtermpath`
table encoding inter-term relationships.

A phase 1 joined query similar to this ERMrest URL can be used to
search for a set of terms:

```
/catalog/N/attribute/P:=cvtermpath/T:=(type_id)/dbxref=REL/pathdistance::lt::10/$P/O:=(object_id)/dbexref=BOUND/S:=(subject_id)/mydomain1/dbxref
```

This query would return a set of distinct dbxref values that are less
than `10` hops below an upper-bound dbxref `BOUND` in the graph of
`REL` relationship (mixed-in with `OBO_REL:is_a` (subclass)
relationship but only if the output terms also appear in the term
domain `mydomain1` which is a subset of all possible terms in the
system.

A phase 2 search can express actual data column constraints to match
on a disjunctive list of terms found by the phase 1 search.  Even if
we implement this on the server, we'd probably do the same two-phase
search, to in-line the bounded term set as a disjunction of constants
(that's our experience with how to get high performance out of
Postgres for complex analytic queries).

Options:

1. Do both search phases on client side with no new ERMrest API
   features.  Might hit some URL length limits eventually.
2. Add a filter syntax to ERMrest API to allow the query triplet of
   (term domain, relationship, and boundary to be encoded as a direct
   predicate on a data column.  E.g. `column::relationship::boundary`
   
Discussion:

To add a query syntactic sugar to ERMrest, we'd need to hard-code a
mapping of directed relationship terms, e.g. `OBO_REL:is_a`, to new
ERMrest predicate operators, e.g. `::subclass_of::` and
`::has_subclass::` so we can express both upper and lower-bounded
constraints against a data column. The right-hand side of the
predicate would specify the boundary value as a dbxref string
(URL-encoded to escape the colon chars). With this sugar, the
`pathdistance` would not be able to be constrained since there is no
reasonable binary predicate syntax to combine relationship type,
boundary, and path-length.

To provide a GUI UX for semantic search, you probably need more than
to choose a relationship and type in dbxref boundary values. You
probably need the equivalent of the phase 1 search to show the user
how the term space expands from a particular combination of boundary
and relationship type while still being limited to the column's term
domain.  In order to present such a UX, you already have to have
client-side detection and awareness of when semantic search is
applicable as well as how to retrieve and preview these term
sub-graphs.

Assuming all the client-side work for a semantic search UX, it is not
clear what value the ERMrest syntactic sugar would add except
robustness against large term sets being encoded in URLs. The
client-side complexity does not change much as long as you need to
guide users through a query-construction UX...

