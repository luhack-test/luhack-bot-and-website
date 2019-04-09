import re

from wtforms import Form, StringField, TextAreaField, Field, validators
from wtforms.widgets import TextInput


class TagListField(Field):
    widget = TextInput()

    def _value(self):
        return " ".join(self.data or ())

    def process_formdata(self, valuelist):
        if valuelist:
            self.data = re.split(r'[^\w-]+', valuelist[0])
        else:
            self.data = []


class WriteupForm(Form):
    title = StringField("Title", [validators.Length(min=4, max=25)])
    tags = TagListField("Tags")
    content = TextAreaField("Content")
