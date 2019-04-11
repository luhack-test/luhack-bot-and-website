import re

from wtforms import Form, StringField, TextAreaField, Field, validators, ValidationError
from wtforms.widgets import TextInput


class TagListField(Field):
    widget = TextInput()

    def _value(self):
        return ", ".join(self.data or ())

    def process_formdata(self, valuelist):
        if valuelist:
            data = filter(
                lambda s: s and not s.isspace(),
                re.split(r"[^\w-]+", valuelist[0].lower()),
            )
            data = list(set(data))
            self.data = data
        else:
            self.data = []

    def post_validate(self, form, validation_stopped):
        for i in self.data:
            l = len(i)
            if l < 3 or l > 20:
                raise ValidationError(
                    "Tags must be between 3 and 20 characters in length"
                )

        if len(self.data) > 8:
            raise ValidationError("Writeups can have at most 8 tags")


class WriteupForm(Form):
    title = StringField("Title", [validators.Length(min=4, max=25)])
    tags = TagListField("Tags")
    content = TextAreaField("Content")
