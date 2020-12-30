import re

import orjson

from wtforms import Form, StringField, TextAreaField, Field, validators, ValidationError
from wtforms.fields.core import BooleanField, IntegerField
from wtforms.widgets import TextInput


invalid_tag_chars = re.compile(r"[^\w-]+")


class TagListField(Field):
    widget = TextInput()

    def _value(self):
        return ", ".join(self.data or ())

    def process_formdata(self, valuelist):
        if valuelist and valuelist[0]:
            tags = [
                invalid_tag_chars.sub("", tag["value"])
                for tag in orjson.loads(valuelist[0])
            ]
            data = list(set(tags))
            self.data = data
        else:
            self.data = []

    def post_validate(self, form, validation_stopped):
        if not self.data:
            return

        for i in self.data:
            l = len(i)
            if l < 3 or l > 20:
                raise ValidationError(
                    "Tags must be between 3 and 20 characters in length"
                )

        if len(self.data) > 8:
            raise ValidationError("Things can have at most 8 tags")


class PostForm(Form):
    title = StringField(
        "Title", [validators.Length(min=4, max=25)]
    )
    tags = TagListField("Tags")
    content = TextAreaField("Content")

class WriteupForm(Form):
    title = StringField(
        "Title", [validators.Length(min=4, max=25)]
    )
    tags = TagListField("Tags")
    private = BooleanField("Private")
    content = TextAreaField("Content")

class ChallengeForm(Form):
    title = StringField(
        "Title", [validators.Length(min=4, max=25)]
    )
    content = TextAreaField("Content")
    flag_or_answer = StringField("Flag/Answer")
    is_flag = BooleanField("Is Flag")
    tags = TagListField("Tags")
    hidden = BooleanField("Hidden")
    depreciated = BooleanField("Depreciated")
    points = IntegerField(
        "Points", [validators.NumberRange(min=1)]
    )

class AnswerForm(Form):
    answer = StringField("Flag/Answer")
