import json, calendar, shutil, sys, os, os.path, glob, shelve, time, pprint, imp, re
from markdown import markdown
from collections import OrderedDict, Counter, namedtuple, MutableMapping
from jinja2 import Environment, FileSystemLoader

if sys.version_info[0] == 2:
    reload(sys)
    sys.setdefaultencoding('utf8')

class Content(object):
    
    def __init__(self, app, path):
        self.app = app
        self.path = path
    
    def load(self):
        pass
    
    def update(self, data):
        pass
    
    def render(self):
        pass

class StaticContent(Content):
    
    def __init__(self, app, path, mappings=None, dependencies=None):
        super(StaticContent, self).__init__(app, path)
        status, val = self.app.cache.get_file(path)
        if status != 'Cached':
            self.app.cache.put_file(path, '')
    
    def load(self):
        return 'Cached'
    
    def render(self):
        path = self.app.get_output_path(self.path, static=True)
        status = self.app.cache.need_update(path, [self.path])
        
        if status != 'Ignore':
            shutil.copy(self.path, path)
        return [(status, path)]

class DynamicContent(Content):

    def __init__(self, app, path, mappings=None, dependencies=None):
        
        super(DynamicContent, self).__init__(app, path)
        
        self.mappings = {}
        if mappings is not None:
            self.mappings = mappings
        self.dependencies = dependencies
    
    def load(self):
        
        self.metadata = None
        self.content = None
        self.data = {}
        self.content_line = 0
        status, val = self.app.cache.get_file(self.path)
        
        if status == 'Cached':
            self.metadata = val['metadata']
            self.content_line = val['content_line']
        else:
            stream = []
            with open(self.app.get_path(self.path)) as f:
                stream = f.readlines()
            
            idx = 0
            lis = [i for (i,x) in enumerate(stream) if x == '}\n']
            if len(lis) > 0:
                idx = lis[0]
            self.content_line = idx+2
            
            metadata = ''.join(stream[:idx+1])
            self.metadata = json.loads(metadata, object_pairs_hook=OrderedDict)
            
            self.app.cache.put_file(self.path, {'metadata': self.metadata, 'content_line': self.content_line})
            
        self.set_url()
        
        return status
    
    def load_content(self):
        stream = []
        with open(self.app.get_path(self.path)) as f:
            stream = f.readlines()[self.content_line:]
        
        self.content = ''.join(stream)
    
    def set_url(self):
        try:
            self.metadata['url'] = self.app.url_for(**self.metadata)
        except Exception:
            pass
    
    def update(self, data):
        
        for (k,v) in data.items():
            key = self.mappings.get(k, k)
            self.data[key] = v
        
        self.data['url_for'] = self.app.url_for
        self.data['len'] = len
        self.data.update(self.metadata)
    
    def render(self):
        
        path = self.app.get_output_path(self.app.url_for(**self.data))
        deps = [self.path]
        if self.dependencies is not None:
            deps.extend(self.dependencies)
        status = self.app.cache.need_update(path, deps)

        if status != 'Ignore':
            if self.content is None:
                self.load_content()
            template = self._render()
            with open(path, 'w') as f:
                f.write(template.render(**self.data))
        
        return [(status, path)]

class Page(DynamicContent):

    def __init__(self, app, path, mappings=None, dependencies=None):
        super(Page, self).__init__(app, path, mappings, dependencies)
    
    def load(self):
        return super(Page, self).load()
    
    def _render(self):
        return self.app.jinja_env.hamlish_from_string(self.content)

class TagPage(DynamicContent):
    
    def __init__(self, app, path, mappings=None, dependencies=None):
        super(TagPage, self).__init__(app, path, mappings, dependencies)
        self.template = None
    
    def load(self):
        return super(TagPage,self).load()
    
    def _render(self):
        if self.template is None:
            self.template = self.app.jinja_env.hamlish_from_string(self.content)
        
        return self.template
    
    def render(self):

        # Special case cause this is expensive
        updated = False
        for dep in (self.dependencies + [self.path]):
            if dep in self.app.cache.updated_content:
                updated = True
        
        if not updated:
            return []
        
        rets = []
        for tag in self.data['tags']:
            self.data['tag'] = tag['tag']
            self.data['tagname'] = tag['tag']
            self.data['tagposts'] = tag['posts']
            rets.extend(super(TagPage, self).render())
        
        return rets

class ReadersCornerPage(DynamicContent):
    
    def __init__(self, app, path, mappings=None, dependencies=None):
        super(ReadersCornerPage, self).__init__(app, path, mappings, dependencies)
        self.template = None
    
    def load(self):
        return super(ReadersCornerPage,self).load()
    
    def _render(self):
        if self.template is None:
            self.template = self.app.jinja_env.hamlish_from_string(self.content)
        
        return self.template
    
    def render(self):

        # Special case cause this is expensive
        updated = False
        for dep in (self.dependencies + [self.path]):
            if dep in self.app.cache.updated_content:
                updated = True

        if not updated:
            return []
        
        rets = []
        archives = self.data['readerscorner']
        for (year, yeararchive) in archives.items():
            for (month, montharchive) in yeararchive.items():
                self.data['year'] = year
                self.data['month'] = month
                self.data['montharchive'] = montharchive
                self.data['monthname'] = calendar.month_name[int(month)]
                rets.extend(super(ReadersCornerPage, self).render())
        
        return rets

class ReadersCornerJSONItem(DynamicContent):
    
    def __init__(self, app, path, mappings=None, dependencies=None):
        super(ReadersCornerJSONItem, self).__init__(app, path, mappings, dependencies)
        self.template = None
        self.renderfn = namedtuple('Template', ['render'])

    def load(self):
        return super(ReadersCornerJSONItem,self).load()
    
    def _render(self):
        def __render(**kwargs):
            return json.dumps(kwargs['entry']).replace('\\n', '<br>')
        return self.renderfn(__render)
    
    def render(self):

        # Special case cause this is expensive
        updated = False
        for dep in (self.dependencies + [self.path]):
            if dep in self.app.cache.updated_content:
                updated = True

        if not updated:
            return []
        
        rets = []
        archives = self.data['readerscorner']
        for (year, yeararchive) in archives.items():
            for (month, montharchive) in yeararchive.items():
                for (day, dayarchive) in montharchive.items():
                    for item in dayarchive:
                        entry = {}
                        for key in ['link', 'name', 'caption', 'description', 'message']:
                            entry[key] = item.get(key, '')
                        self.data['entry'] = entry
                        self.data['id'] = item['id']
                        rets.extend(super(ReadersCornerJSONItem, self).render())
        
        return rets

class BlogPost(DynamicContent):
    
    def __init__(self, app, path, mappings=None, dependencies=None):
        super(BlogPost, self).__init__(app, path, mappings, dependencies)
    
    def load(self):
        status = super(BlogPost, self).load()
        
        year, month, day = self.metadata.get('date', '0000/00/00').split('/')
        self.metadata['year'] = '%d' % int(year)
        self.metadata['month'] = '%02d' % int(month)
        self.metadata['day'] = '%02d' % int(day)
        
        (head, tail) = os.path.split(self.path)
        (root, ext) = os.path.splitext(tail)
        self.metadata['slug'] = root
        
        self.set_url()
        return status
    
    def update(self, data):
        super(BlogPost, self).update(data)
    
    def _render(self):
        content = markdown(self.content)
        
        btemplate = ''
        with open(self.app.get_path(self.data['template'], 'templates')) as f:
            btemplate = f.read()
        
        self.data['content'] = self.app.jinja_env.from_string(content).render()
        return self.app.jinja_env.hamlish_from_string(btemplate)

class Processor(object):
    
    def __init__(self, app):
        self.app = app
    
    def process(self, content):
        pass

class TagList(Processor):
    
    def __init__(self, app, key='tags', datakey='tags', sortkey='date', route='tag', reverse=True):
        super(TagList, self).__init__(app)
        self.key = key
        self.datakey = datakey
        self.sortkey = sortkey
        self.route = route
        self.reverse = reverse
    
    def process(self, content, data):
        
        lis = []
        posts = [c for c in content if type(c) == BlogPost]
        for post in posts:
            lis.extend(post.metadata.get(self.key, []))
        
        tags = []
        for (tag, count) in sorted(Counter(lis).items(), reverse=self.reverse, key=lambda k_v: (k_v[1], k_v[0])):
            tagged = [p.metadata for p in posts if tag in p.metadata[self.datakey]]
            tagged = sorted(tagged, reverse=self.reverse, key=lambda p: p[self.sortkey])
            tags.append(OrderedDict([('tag',tag), ('count',count), ('posts', tagged), ('url', self.app.url_for(self.route, tag=tag))]))
        
        data[self.key] = tags
        return data

class BlogSidebar(Processor):
    
    def __init__(self, app, routes='blogsidebarroutes', routekey='links', tags='tags', key='blogsidebar'):
        super(BlogSidebar, self).__init__(app)
        self.routes = routes
        self.tags = tags
        self.key = key
        self.routekey = routekey
    
    def process(self, content, data):
        
        sidebar = {
            self.routekey : OrderedDict((k,self.app.url_for(v)) for (k,v) in data[self.routes].items()), 
            self.tags : OrderedDict(('%s x %s' % (t['tag'], t['count']), t['url']) for t in data[self.tags])
        }
        
        data[self.key] = sidebar
        return data

class PostList(Processor):
    
    def __init__(self, app, count=5, key='posts', sortkey='date', uniquekey='slug', reverse=True, filters=None, exclude=''):
        super(PostList, self).__init__(app)
        self.count = count
        self.key = key
        self.sortkey = sortkey
        self.uniquekey = uniquekey
        self.reverse = reverse
        self.filters = filters
        self.exclude = exclude
    
    def process(self, content, data):
        
        posts = [c.metadata for c in content if type(c) == BlogPost]
        if self.filters is not None:
            for filter in self.filters:
                posts = [p for p in posts if filter(p)]
        
        ignore = [p[self.uniquekey] for p in data.get(self.exclude, {})]
        posts = [p for p in posts if p[self.uniquekey] not in ignore]
        
        recent = []
        for post in sorted(posts, reverse=self.reverse, key=lambda p: p[self.sortkey])[:self.count]:
            recent.append(post)
        
        data[self.key] = recent
        return data

class PostArchives(Processor):
    
    def __init__(self, app, key='blogarchives', reverse=True):
        super(PostArchives, self).__init__(app)
        self.key = key
        self.reverse = True
    
    def process(self, content, data):
        
        posts = [c for c in content if type(c) == BlogPost]
        years = sorted(k for k in set(p.metadata['year'] for p in posts))
        
        archives = OrderedDict()
        
        for year in years:
            yeararchive = OrderedDict()
            yearposts = [p for p in posts if p.metadata['year'] == year]
            
            months = sorted(k for k in set(p.metadata['month'] for p in yearposts))
            for month in months:
                monthposts = [p for p in yearposts if p.metadata['month'] == month]
                monthposts = sorted(monthposts, reverse=self.reverse, key=lambda p: p.metadata['day'])
                yeararchive[calendar.month_name[int(month)]] = [p.metadata for p in monthposts]
            
            archives[year] = yeararchive
        
        data[self.key] = archives
        return data

class ReadersCorner(Processor):
    
    def __init__(self, app, filename, filter=None, key='readerscorner', sidebarkey='readerscornersidebar', indexkey='readerscornerindex', route='readerscornerpge', homeroute='readerscornerhome', searchroute='readerscornersearch', stopwords=set(), reverse=True):
        super(ReadersCorner, self).__init__(app)
        self.filename = filename
        self.filter = filter
        self.key = key
        self.indexkey = indexkey
        self.sidebarkey = sidebarkey
        self.route = route
        self.homeroute = homeroute
        self.searchroute = searchroute
        self.stopwords = stopwords
        self.reverse = True
    
    def process(self, content, data):

        status, val = self.app.cache.get_file(self.filename)
        if status == 'Cached':
            data[self.key] = val[self.key]
            data[self.sidebarkey] = val[self.sidebarkey]
            data[self.indexkey] = val[self.indexkey]
            return data

        source = []
        with open(self.filename) as input:
            source = json.load(input)

        words = {}
        eid = 0
        patternapos = re.compile("'")
        patternspace = re.compile('_|-')
        patternalnum = re.compile(r'\W+')
        etable = {}
        entries = []
        for entry in source:
            if self.filter is not None:
                entry = self.filter(entry)
                if entry is None:
                    continue
            tm = time.strptime(entry['created_time'], '%Y-%m-%dT%H:%M:%S+0000')
            entry['year'] = tm.tm_year
            entry['month'] = tm.tm_mon
            entry['day'] = tm.tm_mday
            entry['timestamp'] = time.strftime('%H:%M:%S', tm)
            if entry.get('description', '') == 'null':
                entry['description'] = None

            seq = (entry.get(k, '') for k in ['description', 'message', 'link'])
            text = ' '.join(s for s in seq if s is not None)
            text = patternapos.sub('', text)
            text = patternspace.sub(' ', text)
            text = patternalnum.sub(' ', text)
            text = [w for w in text.lower().strip().split() if len(w) > 2]
            text = [w for w in text if w not in self.stopwords]
            entry['text'] = text
            for w in text:
                if w in words:
                    words[w].add(eid)
                else:
                    words[w] = set([eid])

            entry['id'] = eid
            etable[eid] = entry
            eid = eid + 1
            entries.append(entry)

        _index = OrderedDict()
        for word, results in sorted(words.items(), key = lambda wr: wr[0]):
            _index[word] = sorted([r for r in results], key = lambda r: etable[r]['created_time'], reverse = self.reverse)
        index = json.dumps(_index)
        
        years = sorted((k for k in set(e['year'] for e in entries)), reverse=self.reverse)

        archives = OrderedDict()
        sidebar = OrderedDict()

        sidebar['Main'] = OrderedDict()
        sidebar['Main']['Home'] = self.app.url_for(self.homeroute)
        sidebar['Main']['Search'] = self.app.url_for(self.searchroute)
        
        for year in years:
            yeararchive = OrderedDict()
            sidebar[year] = OrderedDict()
            yearentries = [e for e in entries if e['year'] == year]
            
            months = sorted((k for k in set(e['month'] for e in yearentries)), reverse=self.reverse)
            for month in months:
                montharchive = OrderedDict()
                monthentries = [e for e in yearentries if e['month'] == month]
                days = sorted((k for k in set(e['day'] for e in monthentries)), reverse=self.reverse)
                for day in days:
                    dayentries = [e for e in monthentries if e['day'] == day]
                    montharchive[day] = sorted(dayentries, reverse=self.reverse, key=lambda e: e['timestamp'])
                yeararchive[month] = montharchive
                linkstring = '%s (%s)' % (calendar.month_name[int(month)], sum(len(v) for k,v in montharchive.items()))
                sidebar[year][linkstring] = self.app.url_for(self.route, year=year, month=month)
            
            archives[year] = yeararchive

        data[self.key] = archives
        data[self.sidebarkey] = sidebar
        data[self.indexkey] = index
        self.app.cache.put_file(self.filename, {self.key : archives, self.sidebarkey : sidebar, self.indexkey : index})

        return data

class RSSFeed(Processor):
    
    def __init__(self, app, count=5, key='blogrss', title='title', link='link', description='description', sortkey='date', reverse=True):
        super(RSSFeed, self).__init__(app)
        self.key = key
        self.title = title
        self.link = link
        self.description = description
        self.count = count
        self.sortkey = sortkey
        self.reverse = True
    
    def process(self, content, data):
        
        posts = [c for c in content if type(c) == BlogPost]
        map = {'title' : 'title', 'description' : 'excerpt', 'link' : 'url'}
        
        items = []
        for p in sorted(posts, reverse=self.reverse, key=lambda p: p.metadata[self.sortkey])[:self.count]:
            items.append(dict((k,p.metadata.get(map[k])) for k in map.keys()))
        
        feed = dict(title=self.title, link=self.link, description=self.description, items=items)
        
        data[self.key] = feed
        return data

class Sitemap(Processor):
    
    def __init__(self, app, root='', key='sitemap'):
        super(Sitemap, self).__init__(app)
        self.key = key
        self.root = root
    
    def process(self, content, data):
        
        urls = []
        for item in (c for c in content if (type(c) != TagPage) and (type(c) != StaticContent) and (type(c) != ReadersCornerPage) and (type(c) != ReadersCornerJSONItem)):
            url = self.root + self.app.get_output_path(self.app.url_for(**item.metadata)).replace(self.app.directories['output'], '')
            urls.append(url)
        
        data[self.key] = urls
        return data

class CacheDict(MutableMapping):

    def __init__(self, path, *args, **kwargs):
        self.store = dict()
        self.path = path

        if os.path.exists(path):
            self.store.update(json.loads(open(path).read()))

        self.update(dict(*args, **kwargs))

    def __getitem__(self, key):
        return self.store[key]

    def __setitem__(self, key, value):
        self.store[key] = value

    def __delitem__(self, key):
        del self.store[key]

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def close(self):
        with open(self.path, 'w') as output:
            output.write(json.dumps(self.store))

class Cache(object):
    
    def __init__(self, path):
        self.store = CacheDict(path)
        self.updated_content = []
        self.mtimes = {}
    
    def get_file(self, path):
        val = None
        status = 'Read'
        
        key = path
        if key not in self.store:
            return (status, val)
        
        mtime = os.path.getmtime(path)
        val = self.store[key]
        
        if mtime < val['mtime']:
            status = 'Cached'
            val = val['value']

        if status == 'Read':
            self.updated_content.append(path)
        
        return (status, val)
    
    def put_file(self, path, value):
        key = path
        val = {'mtime': int(time.time()), 'value': value}
        
        self.store[key] = val
        self.mtimes[path] = val['mtime']

    def put_content(self, name, value):
        key = name
        val = {'mtime': int(time.time()), 'value': value}
        
        v = self.store.get(key, {'value': None})
        if v['value'] != value:
            self.store[key] = val
            self.updated_content.append(name)
            self.mtimes[name] = val['mtime']
    
    def need_update(self, path, dependencies=None):
        if not os.path.exists(path):
            return 'Create'
        mtime = os.path.getmtime(path)
        
        deps = []
        if dependencies is not None:
            deps.extend(dependencies)
        
        mtimes = [0]
        for dep in deps:
            if dep in self.mtimes:
                mtimes.append(self.mtimes[dep])
            else:
                mtimes.append(self.store.get(dep, {'mtime': 0})['mtime'])
                self.mtimes[dep] = mtimes[-1]
        
        if mtime < max(mtimes):
            return 'Modified'

        for dep in dependencies:
            if dep in self.updated_content:
                return 'Modified'

        return 'Ignore'
    
    def shutdown(self):
        self.store.close()

class Engine(object):
    
    def __init__(self, directories, routes, sources, processors, data, verbose=False):
        self.directories = directories
        self.routes = routes
        self.sources = sources
        self.processors = processors
        self.data = data
        self.verbose = verbose
        
        self.content = []
        self.cache = Cache('cache')
        
        self.jinja_env = Environment(extensions=['jinja2.ext.autoescape', 'jinja2.ext.with_', 'hamlish_jinja.HamlishExtension'])
        self.jinja_env.loader = FileSystemLoader(self.directories['templates'])
        self.jinja_env.hamlish_enable_div_shortcut = True
        self.jinja_env.hamlish_mode = 'debug'
        self.jinja_env.hamlish_file_extensions=('.haml','.xml')
        
        for path in glob.glob(self.directories['templates'] + os.sep + '*'):
            status, val = self.cache.get_file(path)
            if status != 'Cached':
                self.cache.put_file(path, '')

    def get_path(self, path, resource=None):
        if resource is not None:
            return os.path.join(self.directories[resource], path)
        return path
    
    def get_output_path(self, path, static=False):
        (root, ext) = os.path.splitext(path)
        root = (self.directories['output'] + os.sep + root).replace('%s%s' % (os.sep, os.sep), os.sep)
        if ext == '':
            ext = os.sep + 'index.html'
        if os.path.basename(path) != '':
            root, tmp = os.path.split(root)
            ext = tmp + ext
            root = root + os.sep
        if not os.path.exists(root):
            os.makedirs(root)
        return (root + ext).replace('%s%s' % (os.sep, os.sep), os.sep)
    
    def url_for(self, route, **kwargs):
        return self.routes[route].format(**kwargs)

    def load_content(self):
        print('Loading content ...')
        count = 0
        cached = 0
        start = time.time()
        for type, expr, mappings, dependencies in self.sources:
            cons = getattr(sys.modules[__name__], type)
            for path in [p for p in glob.glob(expr) if not os.path.isdir(p)]:
                item = cons(self, path, mappings, dependencies)
                status = item.load()
                if status != 'Cached' or self.verbose:
                    print('[%s] %s' % (status, path))
                else:
                    cached += 1
                self.content.append(item)
                count += 1
        print('Loaded {} items ({} cached) in {:.2f}s.'.format(count, cached, time.time()-start))
    
    def process_content(self):
        print('Processing content ...')
        start = time.time()
        count = 0
        for (type, kwargs) in self.processors:
            if self.verbose:
                print('Processing %s' % type)
            processor = getattr(sys.modules[__name__], type)(self, **kwargs)
            self.data.update(processor.process(self.content, self.data))
            count += 1
        for key,val in self.data.items():
            self.cache.put_content(key, val)
        print('Ran {} processors in {:.2f}s.'.format(count, time.time()-start))
    
    def generate_output(self):
        print('Generating output ...')
        count = 0
        cached = 0
        start = time.time()
        for content in self.content:
            content.update(self.data)
            for (status, path) in content.render():
                if status != 'Ignore' or self.verbose:
                    print('[%s] %s' % (status, path))
                else:
                    cached += 1
                count += 1
        print('Generated {} items ({} cached) in {:.2f}s.'.format(count, cached, time.time()-start))
    
    def generate(self):
        self.load_content()
        self.process_content()
        self.generate_output()
        self.cache.shutdown()

if __name__ == '__main__':
    filename = sys.argv[1]
    settings = imp.load_source('settings', filename)
    engine = Engine(settings.directories, settings.routes, settings.sources, settings.processors, settings.data)
    engine.generate()
