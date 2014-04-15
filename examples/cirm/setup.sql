CREATE SCHEMA "CIRM";

CREATE TABLE "CIRM"."Box"
  (
    "ID" varchar(30) PRIMARY KEY,
    "Section Date" date NOT NULL,
    "Sample Name" varchar(15) NOT NULL,
    "Initials" varchar(3) NOT NULL,
    "Disambiguator" char(1) NOT NULL,
    "Comment" text,
    "Tags" text
  );

-- these indices must match the expression generated by src/model.py:FreetextColumn to be useful
-- need same columns (all text and character types)
-- need same typecasts
-- need same coalescing of NULLs
-- need same concatenation order (based on table column ordinal)
CREATE INDEX ON "CIRM"."Box" USING gin ( 
  (to_tsvector('english'::regconfig, 
  	       COALESCE("ID"::text, ''::text) 
	       || ' ' || COALESCE("Sample Name"::text, ''::text) 
	       || ' ' || COALESCE("Initials"::text, ''::text) 
	       || ' ' || COALESCE("Disambiguator"::text, ''::text) 
	       || ' ' || COALESCE("Comment"::text, ''::text) 
	       || ' ' || COALESCE("Tags"::text, ''::text)
	      )
  ) 
);

CREATE TABLE "CIRM"."Experiment"
  (
    "ID" varchar(30) PRIMARY KEY,
    "Experiment Date" date NOT NULL,
    "Experiment Description" varchar(15) NOT NULL,
    "Initials" varchar(3) NOT NULL,
    "Disambiguator" char(1) NOT NULL,
    "Comment" text,
    "Tags" text
  );

CREATE INDEX ON "CIRM"."Experiment" USING gin ( 
  (to_tsvector('english'::regconfig, 
  	       COALESCE("ID"::text, ''::text) 
	       || ' ' || COALESCE("Experiment Description"::text, ''::text) 
	       || ' ' || COALESCE("Initials"::text, ''::text) 
	       || ' ' || COALESCE("Disambiguator"::text, ''::text) 
	       || ' ' || COALESCE("Comment"::text, ''::text) 
	       || ' ' || COALESCE("Tags"::text, ''::text)
	      )
  ) 
);

CREATE TABLE "CIRM"."Slide"
  (
    "ID" varchar(37) PRIMARY KEY,
    "Seq." integer NOT NULL,
    "Rev." integer NOT NULL,
    "Box ID" varchar(30) NOT NULL,
    "Experiment ID" varchar(30) DEFAULT NULL,
    "Comment" text,
    "Tags" text,
    FOREIGN KEY ("Box ID") REFERENCES "CIRM"."Box" ("ID"),
    FOREIGN KEY ("Experiment ID") REFERENCES "CIRM"."Experiment" ("ID") ON DELETE SET DEFAULT
  );

CREATE INDEX ON "CIRM"."Slide" USING gin ( 
  (to_tsvector('english'::regconfig, 
  	       COALESCE("ID"::text, ''::text) 
	       || ' ' || COALESCE("Box ID"::text, ''::text) 
	       || ' ' || COALESCE("Experiment ID"::text, ''::text) 
	       || ' ' || COALESCE("Comment"::text, ''::text) 
	       || ' ' || COALESCE("Tags"::text, ''::text)
	      )
  ) 
);


CREATE TABLE "CIRM"."Scan"
  (
    "ID" text PRIMARY KEY,
    "Slide ID" varchar(37) NOT NULL,
    "Original Filename" text,
    "GO Endpoint" text,
    "GO Path" text,
    "HTTP URL" text,
    "Filename" text,
    "File Size" bigint,
    "Thumbnail" text,
    "Zoomify" text,
    "Comment" text,
    "Tags" text,
    FOREIGN KEY ("Slide ID") REFERENCES "CIRM"."Slide" ("ID")
  );

CREATE INDEX ON "CIRM"."Scan" USING gin ( 
  (to_tsvector('english'::regconfig, 
  	       COALESCE("ID"::text, ''::text) 
	       || ' ' || COALESCE("Slide ID"::text, ''::text) 
	       || ' ' || COALESCE("Original Filename"::text, ''::text) 
	       || ' ' || COALESCE("GO Endpoint"::text, ''::text) 
	       || ' ' || COALESCE("GO Path"::text, ''::text) 
	       || ' ' || COALESCE("HTTP URL"::text, ''::text) 
	       || ' ' || COALESCE("Filename"::text, ''::text) 
	       || ' ' || COALESCE("Thumbnail"::text, ''::text) 
	       || ' ' || COALESCE("Zoomify"::text, ''::text) 
	       || ' ' || COALESCE("Comment"::text, ''::text) 
	       || ' ' || COALESCE("Tags"::text, ''::text)
	      )
  ) 
);

SET client_min_messages=ERROR;
VACUUM ANALYZE;

