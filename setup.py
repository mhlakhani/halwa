from setuptools import setup
setup(
    name = "Halwa",
    version = "0.1.9",
    py_modules = ['halwa'],

    install_requires = ['Hamlish-Jinja>=0.3.0','Jinja2>=2.6', 'Markdown>=2.2.1'],

    package_data = {
        '': ['*.md'],
    },
    zip_safe = True,

    # metadata for upload to PyPI
    author = "Hasnain Lakhani",
    author_email = "m.hasnain.lakhani@gmail.com",
    description = "Single file static site generator.",
    keywords = "static site generator",
    url = "https://github.com/mhlakhani/halwa",
    download_url = "git+https://github.com/mhlakhani/halwa.git"

)
