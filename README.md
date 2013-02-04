Halwa - A Static Site Generator
=================================

Halwa is a single file static site generator written in Python. It's light-weight and the only dependencies are jinja2, hamlish-jinja, and markdown.

Usage
-----

Using Halwa is as easy as it should be; install it, then create a configuration file and point Halwa to it:

> pip install halwa

> python -m halwa config.py

Overview
--------

Halwa is organized around two main things, *content* and *processors*. A piece of content is a data source (static HTML, HAML, or Markdown) which is eventually converted into an output page (or pages). Halwa uses the following workflow:

1. Initialize a global data dictionary.
2. Load each piece of content specified in *sources*.
3. Run each of the processors specified in *processors*, generating output that goes into the data dictionary.
4. Update each piece of content with the contents of the data dictionary.
5. Render each piece of content, writing it out to the output folder.

A sample configuration is available at [https://github.com/mhlakhani/mhlakhani-com](https://github.com/mhlakhani/mhlakhani-com).

Configuration
-------------

The configuration file is a pure python file. The following variables must be set:

### directories
This is a dictionary that must contain two keys, one for the the *templates* directory, and another for the *output* directory.

### routes
A dictionary containing route definitions for various pieces of content. The key is the route name, and the value is a format string (which will be filled in by the content's metadata). For example, the route '/blog/{tag}' will have '{tag}' replaced by the tag field in the content's metadata.

### sources
A list of 4-tuples, each describing a piece of content. A sample source tuple is below:

> ('Page', 'content/blog*.haml', {'blogsidebar' : 'sidebar'}, ['tags'])

The entries are as follows:

1. The type of content.
2. The path for source files that should be used (any 'glob' expression is valid here). 
3. The set of mappings, each key in the global 'data' object will be mapped to the corresponding key given here, for the purposes of this content object; before the content's data field is updated.
4. A list of keys in the global data object that this content object depends on. This is used for resolving caching dependencies; since templates may depend on arbitrary data items.

### processors
A list of tuples, specifying which processors should be run. A sample entry is below:

> ('PostArchives', {'key' : 'blogarchives'})

The first item is the name of the processor to run, the second item is a dictionary which is used to provide settings for the processor.

### data
The initial dictionary to be used to fill the *data* dictionary.

Content
-------

There are multiple types of content that can be defined. They are described below.

### StaticContent

This will copy the source file to the corresponding path in the output directory.

### DynamicContent

This is the base class for all the following content objects. It will read the input file, and parse
the JSON dictionary at the top, which will be set as the content's metadata. The rest of the data
will be parsed as content. It expects a *route* attribute in the metadata at the very least, to generate
the output URL for the content. It will render the page as a Hamlish Jinja template and write it to the appropriate directory.

### Page

It will simply render the given template. It is intended for simple pages (such as an index).

### TagPage

This will take each *tag* in the *tags* dictionary that has been passed in, and render the template page
with that *tag*.

### BlogPost

This will automatically generate a *slug* for the content, based on the date in the metadata and the filename.
The content will be passed through markdown before being passed to the Hamlish Jinja renderer.

Processors
----------

These process the *data* dictionary after all the metadata has been loaded from the content; and then put
the processed results back in so that dynamic pages can be based on those.

### TagList

This processor will look for the *key* attribute in each post (e.g. "tags"); which should be a list of values.
It will make a dictionary where each unique value maps to the list of posts that contain this value. The final
output will be stored in the *datakey* attribute of the *data* dictionary. It will sort the posts by the *sortkey*
attribute (in reverse order if *reverse* is true).

### BlogSidebar

This processor will take the routes given in the *routes* attribute of the *data* dictionary, the tags given in the *tags* attribute of the *data* dictionary, and create a dictionary that contains the routes, their URLs, and a list of tags with their counts.

### PostList

This processor will generate a list of posts and put them in the *key* attribute of the *data* dictionary. It will
have *count* posts, sorted by *sortkey* (in reverse order if *reverse* is true), use *uniquekey* to determine unique posts, apply each function in *filters* to see which posts should be included (it should pass all filters); and exclude each post in *exclude*.

### PostArchives

This processor generates post archives, saving them in the *key* attribute of the *data* dictionary. The archive
is a dictionary (of years), where each year is a dictionary (of months); and each month is a dictionary of posts
in that month, sorted by day (in reverse order if *reverse* is true).

### RSSFeed

This processor generates an RSSFeed, putting it in the *key* attribute of the *data* dictionary. It will put
*count* posts, sorted by the *sortkey* attribute (in reverse order if *reverse* is true). 

### Sitemap

This processor generates a list of URLs and stores it in the *key* attribute of the *data* dictionary.

Caching
-------

Halwa has support for some simple caching to make incremental site builds faster. 

When content is initially read from disk, the loaded metadata is stored in the cache. Later reads of the metadata will come from the cache if the file on disk has not been modified.

Before content is written to disk, its dependencies are checked (the source file on disk is a default dependency). If any of the dependencies have been modified at a time later than the time
the existing output file (if any) was written, the output file will be re-generated. Otherwise it will be left alone.

The caching manager can not know whether any of the templates or processors depend on some user-defined keys in the *data* dictionary. In order to help it out, the *dependencies* list can be filled in. This is especially useful for specifying which templates a piece of content depends on (if you're using jinja template inheritance) as then it will re-generate output when the source template changes. Templates are added automatically to the cache, with the key "TEMPLATE_DIR/filename".
