import werkzeug
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField, SelectField, BooleanField, TextAreaField
from wtforms.validators import DataRequired
from adscore import api

class ModernForm(FlaskForm):
    q = StringField('q', validators=[DataRequired()])
    sort = StringField('sort', default="date desc")
    rows = IntegerField('rows', default=25)
    start = IntegerField('start', default=0)
    p_ = IntegerField('p_', default=0)
    submit = SubmitField('Search')

    @classmethod
    def parse(cls, params):
        """
        Create a ModernForm object by parsing the provided parameters, which
        can be a ImmutableMultiDict as built by Flask or a string to be parsed
        by this method
        """
        if type(params) is str:
            # For compatibility with BBB, accept parameters that are embbeded in the
            # URL without a question mark
            parsed = urllib.parse.parse_qs(params)
            # parse_qa will create a list for single strings such as {'q': ['star']},
            # extract them if there is only one element:
            parsed = dict( (k, v if len(v) > 1 else v[0] ) for k, v in parsed.items() )
            form = cls(**parsed) # ModernForm
        elif type(params) is werkzeug.datastructures.ImmutableMultiDict:
            form = cls(params) # ModernForm
        else:
            raise Exception("Unknown search parameters type")
        # Sanitize numeric parameters (positive integers)
        for numeric_param in ('rows', 'start', 'p_'):
            try:
                getattr(form, numeric_param).data = max(0, int(getattr(form, numeric_param).data))
            except:
                getattr(form, numeric_param).data = getattr(ModernForm, numeric_param).kwargs.get('default', 0)
        if form.rows.data == 0:
            # Make sure the rows parameter is not zero, otherwise division by zero can happen
            form.rows.data = getattr(ModernForm, numeric_param).kwargs.get('default', 0)
        return form

class PaperForm(FlaskForm):
    bibcodes = TextAreaField('bibcodes')
    bibstem = StringField('bibstem')
    year = IntegerField('year')
    volume = IntegerField('volume')
    page = IntegerField('page')

    def build_query(self):
        """
        Build query to be send to the main search endpoint
        """
        if self.bibcodes.data:
            bibcode_list = self.bibcodes.data.split()
            if len(bibcode_list) > 0:
                # Store query and get QID
                results = api.store_query(self.bibcodes.data.split()) # Split will get rid of \r\n
                query = "docs({})".format(results['qid'])
                return query
            else:
                return ""
        else:
            query = []
            if self.bibstem.data:
                query.append("bibstem:({})".format(self.bibstem.data))
            if self.year.data:
                query.append("year:{}".format(self.year.data))
            if self.volume.data:
                query.append("volume:{}".format(self.volume.data))
            if self.page.data:
                query.append("page:{}".format(self.page.data))
            return " ".join(query)

class ClassicForm(FlaskForm):
    astronomy = BooleanField('astronomy', default=True)
    physics = BooleanField('physics', default=False)
    refereed = BooleanField('refereed', default=False)
    article = BooleanField('article', default=False)
    author_logic = StringField('author_logic', default="AND")
    author_names = StringField('author_names')
    object_logic = StringField('object_logic', default="AND")
    object_names = StringField('object_names')
    month_from = IntegerField('month_from')
    year_from = IntegerField('year_from')
    month_to = IntegerField('month_to')
    year_to = IntegerField('year_to')
    title_logic = StringField('title_logic', default="AND")
    title = StringField('title')
    abstract_logic = StringField('abstract_logic', default="AND")
    abstract = StringField('abstract')
    bibstem = StringField('bibstem')

    def _authors(self):
        authors = self.author_names.data.split()
        if self.author_logic.data == "OR":
            return "author:({})".format(" OR ".join(["\"{}\"".format(a) for a in authors]))
        elif self.author_logic.data == "AND":
            return "author:({})".format(" ".join(["\"{}\"".format(a) for a in authors]))
        else:
            return "author:({})".format(" ".join(authors))

    def _objects(self):
        # TODO: form.object_logic.data is not used (not even in BBB)
        objects = self.object_names.data.split()
        results = api.objects_query(objects)
        transformed_objects_query = results.get('query')
        if transformed_objects_query:
            return transformed_objects_query
        else:
            return ""

    def _pubdate(self):
        year_from = min(max(self.year_from.data, 0), 9999) if self.year_from.data else 0
        year_to = min(max(self.year_to.data, 0), 9999) if self.year_to.data else 9999
        month_from = min(max(self.month_from.data, 1), 12) if self.month_from.data else 1
        month_to = min(max(self.month_to.data, 1), 12) if self.month_to.data else 12
        pubdate = "pubdate:[{:04}-{:02} TO {:04}-{:02}]".format(year_from, month_from, year_to, month_to)
        if pubdate != "pubdate:[0000-01 TO 9999-12]":
            return pubdate
        else:
            return ""

    def _title(self):
        titles = self.title.data.split()
        if self.title_logic.data == "OR":
            return " OR ".join(["title:({})".format(a) for a in titles])
        elif self.title_logic.data == "AND":
            return " ".join(["title:({})".format(a) for a in titles])
        else:
            return "title:({})".format(" ".join(titles))

    def _abstract(self):
        abstracts = self.abstract.data.split()
        if self.abstract_logic.data == "OR":
            return " OR ".join(["abstract:({})".format(a) for a in abstracts])
        elif self.abstract_logic.data == "AND":
            return " ".join(["abstract:({})".format(a) for a in abstracts])
        else:
            return "abs:({})".format(" ".join(abstracts))

    def _bistem(self):
        bibstems = self.bibstem.data.split(",")
        return " OR ".join(["bibstem:({})".format(b) for b in bibstems])

    def build_query(self):
        """
        Build query to be send to the main search endpoint
        """
        query = []
        if self.astronomy.data:
            query.append("database:astronomy")
        if self.physics.data:
            query.append("database:physics")
        if query:
            query = [" OR ".join(query)]
        if self.refereed.data:
            query.append("property:refereed")
        if self.article.data:
            query.append("property:article")
        if self.author_names.data:
            query.append(self._authors())
        if self.object_names.data:
            query.append(self._objects())
        if self.year_from.data or self.year_to.data or self.month_from.data or self.month_to.data:
            query.append(self._pubdate())
        if self.title.data:
            query.append(self._title())
        if self.abstract.data:
            query.append(self._abstract())
        if self.bibstem.data:
            query.append(self._bibstem())
        return " ".join(query)
