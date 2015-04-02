# -*- coding: utf-8 -*-
__author__ = 'Most Wanted'

import os
import sys
import logging
import shutil
import peewee
import wtforms
import inspect
import pyclbr
import importlib


from playhouse.reflection import Introspector
from peewee import print_, MySQLDatabase
from jinja2 import Template


from .helpers import to_file


logger = logging.getLogger(__name__)

FORMS_FILE = 'benedict/app/gen_forms.py'
VIEWS_FILE = 'benedict/app/gen_views.py'

PEEWEE_TO_WTFORMS = {
    peewee.CharField: wtforms.StringField,
    peewee.IntegerField: wtforms.IntegerField,
    peewee.BooleanField: wtforms.BooleanField,
    peewee.DateTimeField: wtforms.DateTimeField
}


class Generator(object):

    def __init__(self, module_name=None, project_name=None):
        pass

    def introspect(self):
        db = MySQLDatabase('bmgtest', host='127.0.0.1', port=3306, user='root', password='')
        introspector = Introspector.from_database(db)
        with to_file('benedict/app/models.py'):
            self.print_models(introspector)

    def print_models(self, introspector, tables=None):
        database = introspector.introspect()
        print_('')
        print_('')

        def _print_table(table, seen, accum=None):
            accum = accum or []
            foreign_keys = database.foreign_keys[table]
            for foreign_key in foreign_keys:
                dest = foreign_key.dest_table

                # In the event the destination table has already been pushed
                # for printing, then we have a reference cycle.
                if dest in accum and table not in accum:
                    print_('# Possible reference cycle: %s' % dest)

                # If this is not a self-referential foreign key, and we have
                # not already processed the destination table, do so now.
                if dest not in seen and dest not in accum:
                    seen.add(dest)
                    if dest != table:
                        _print_table(dest, seen, accum + [table])

            print_('class %s(BaseModel):' % database.model_names[table])
            columns = database.columns[table]
            primary_keys = database.primary_keys[table]
            for name, column in sorted(columns.items()):
                skip = all([
                    name == 'id',
                    len(primary_keys) == 1,
                    column.field_class in introspector.pk_classes])
                if skip:
                    continue
                if column.primary_key and len(primary_keys) > 1:
                    # If we have a CompositeKey, then we do not want to explicitly
                    # mark the columns as being primary keys.
                    column.primary_key = False

                print_('    %s' % column.get_field())

            print_('')
            print_('    class Meta:')
            print_('        db_table = \'%s\'' % table)
            if introspector.schema:
                print_('        schema = \'%s\'' % introspector.schema)
            if len(primary_keys) > 1:
                pk_field_names = sorted([
                    field.name for col, field in columns.items()
                    if col in primary_keys])
                pk_list = ', '.join("'%s'" % pk for pk in pk_field_names)
                print_('        primary_key = CompositeKey(%s)' % pk_list)
            print_('')

            seen.add(table)

        seen = set()
        for table in sorted(database.model_names.keys()):
            if table not in seen:
                if not tables or table in tables:
                    _print_table(table, seen)

    def get_models(self, models_file):
        result = []
        module_name = os.path.splitext(models_file)[0]
        module = 'app.%s' % module_name
        pyclbr._modules = {}  # Clear cache
        m = pyclbr.readmodule(module, path=['benedict'])  #todo: project_name
        logger.info('Checking module %s for peewee-models' % models_file)
        for value in m.itervalues():
            if value.module == module:
                if hasattr(value, 'super'):
                    base = value.super[0]
                    if hasattr(base, 'name') and base.name == 'BaseModel':
                        result.append(value.name)
        return result

    def generate_model_data(self, module_name=None, model_name=None):
        self.create_files()

        sys.path.insert(0, 'benedict')  #todo: project_name
        models = importlib.import_module('app.models')  #todo: models-file name
        print('Here')
        for name, obj in inspect.getmembers(models, inspect.isclass):
            if obj.__module__ == models.__name__:
                print(obj.__name__, model_name)
                if obj.__name__ == model_name:
                    logger.info('Going for %s' % model_name)
                    self._create(obj)

    def generate_view(self, view_name, model_name):
        #log action
        v = ViewCreator(view_name, model_name)
        v.write()

    def create_files(self):
        if not os.path.exists(FORMS_FILE):
            logger.info('Initial creating of generated forms file')
            shutil.copyfile('boilerplate/app/forms_header.py', 'benedict/app/gen_forms.py')  #todo: project name

        if not os.path.exists(VIEWS_FILE):
            logger.info('Initial creating of generated views file')
            shutil.copyfile('boilerplate/app/views_header.py', 'benedict/app/gen_views.py')  #todo: project name

    def _create(self, obj):
        logger.info('Creating all for %s' % obj.__name__)
        new_form_name = obj.__name__ + 'Form'  # e.g. UserForm
        new_view_name = obj.__name__.lower()

        #new_form_class = type(new_form_name, (wtforms.Form, ), {})
        f = FormsCreator(new_form_name)
        for field_name, field in vars(obj).iteritems():
            if isinstance(field, peewee.FieldDescriptor):
                for key in PEEWEE_TO_WTFORMS.iterkeys():
                    if key is type(field.field):
                        f.add_field(field_name, PEEWEE_TO_WTFORMS[key].__name__)
                        #setattr(new_form_class, field_name, PEEWEE_TO_WTFORMS[key])
                        #print('%s -> %s' % (field.field, PEEWEE_TO_WTFORMS[key]))
        #print(j.render())
        f.write()
        self.generate_view(new_view_name, obj.__name__)


class ViewCreator():
    template = """


@app.route('/{{ view_name }}_admin', method=['GET', 'POST'])
def {{ view_name }}_admin():
    template = env.get_template('gen_views/{{ view_name }}_admin.html')
    form = {{ peewee_model }}Form(request.POST)
    items = {{ peewee_model }}.select()
    if request.method == 'POST':
        if form.validate():
            new_item = {{ peewee_model }}.create(**form.data)
            form = {{ peewee_model }}Form()
    return template.render(items=items, form=form)


@app.route('/{{ view_name }}_admin/edit/<{{ view_name }}_id:int>', method=['GET', 'POST'])
def {{ view_name }}_edit({{ view_name }}_id):
    item = {{ peewee_model }}.get_or_404({{ peewee_model }}.id == {{ view_name }}_id)
    if request.method == 'GET':
        return json.dumps(item, cls=PeeweeModelEncoder)

    form = {{ peewee_model }}Form(request.POST)
    if form.validate():
        for attr, value in form.data.iteritems():
            setattr(item, attr, value)
        item.save()
        redirect('/{{ view_name }}_admin')

    items = {{ peewee_model }}.select()
    template = env.get_template('gen_views/{{ view_name }}_admin.html')
    return template.render(items=items, form=form)


@app.get('/{{ view_name }}_admin/delete/<{{ view_name }}_id:int>')
def {{ view_name }}_delete({{ view_name }}_id):
    item = {{ peewee_model }}.get({{ peewee_model }}.id == {{ view_name }}_id)
    item.delete_instance()
    return json.dumps({
        'status': 'success',
        'message': 'Item was deleted'
    })
"""

    def __init__(self, name, peewee_model):
        self.name = name
        self.peewee_model = peewee_model

    def write(self):
        t = Template(self.template)
        bottle_view = t.render(view_name=self.name,
                               peewee_model=self.peewee_model)
        with open(VIEWS_FILE, 'a') as fout:
            fout.writelines(bottle_view)

        destination = 'benedict/templates/gen_views'  #todo: project name
        if not os.path.exists(destination):
            os.makedirs(destination)
        self.create_template(destination)

    def create_template(self, dest):
        templates_dir = 'boilerplate/templates/kube' #todo: you know not kube
        shutil.copyfile('{0}/blueprint.html'.format(templates_dir),
                 '{0}/{1}_admin.html'.format(dest, self.name))


class FormsCreator():
    template = """


class {{ class_name }}(Form):
    {% for field in class_fields %}{{ field.name }} = wtforms.{{ field.type_}}(validators=[validators.InputRequired()])
    {% endfor %}
"""

    def __init__(self, name):
        self.name = name
        self.fields = []

    def add_field(self, field_name, field_type):
        self.fields.append({'name': field_name, 'type_': field_type})

    def render(self):
        t = Template(self.template)
        return t.render(class_name=self.name, class_fields=self.fields)

    def write(self):
        with open(FORMS_FILE, 'a') as fout:
            fout.writelines(self.render())