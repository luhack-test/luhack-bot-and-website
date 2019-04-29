import re

import ujson

from wtforms import Form, StringField, TextAreaField, Field, validators, ValidationError
from wtforms.widgets import TextInput


invalid_tag_chars = re.compile(r"[^\w-]+")


class TagListField(Field):
    widget = TextInput()

    def _value(self):
        return ", ".join(self.data or ())

    def process_formdata(self, valuelist):
        if valuelist:
            tags = [invalid_tag_chars.sub("", tag["value"]) for tag in ujson.decode(valuelist[0])]
            data = list(set(tags))
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


class PostForm(Form):
    title = StringField("Title", [validators.Length(min=4, max=25)])
    tags = TagListField("Tags")
    content = TextAreaField("Content")
