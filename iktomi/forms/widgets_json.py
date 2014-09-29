# -*- coding: utf-8 -*-

from . import convs
from .widgets import Widget
from iktomi.utils import cached_property

class Widget(Widget):

    @cached_property
    def widget_name(self):
        return type(self).__name__

    def render(self):
        return dict(widget=self.widget_name,
                    key=self.field.name,
                    render_type=self.render_type,
                    label=self.field.label or '',
                    hint=self.field.hint or '',
                    id=self.field.id,
                    input_name=self.field.input_name,
                    required=self.field.conv.required,
                    multiple=self.multiple,
                    classname=self.classname)


class TextInput(Widget):

    classname = 'textinput'


class Textarea(Widget):
    pass


class HiddenInput(Widget):

    render_type = 'hidden'


class PasswordInput(Widget):

    classname = 'textinput'


class Select(Widget):
    classname = None
    #: HTML select element's select attribute value.
    size = None
    #: Label assigned to None value if field is not required
    null_label = '--------'

    def get_options(self):
        options = []
        # XXX ugly
        choice_conv = self.field.conv
        if isinstance(choice_conv, convs.ListOf):
            choice_conv = choice_conv.conv
        assert isinstance(choice_conv, convs.EnumChoice)

        for choice, label in choice_conv.options():
            options.append(dict(value=unicode(choice),
                                title=label))
        return options

    def render(self):
        return dict(super(Select, self).render(),
                    size=self.size,
                    null_label=self.null_label,
                    options=self.get_options())


class CheckBoxSelect(Select):

    classname = 'select-checkbox'


class CheckBox(Widget):

    render_type = 'checkbox'


class CharDisplay(Widget):

    classname = 'chardisplay'
    #: If is True, value is escaped while rendering. 
    #: Passed to template as :obj:`should_escape` variable.
    escape = True
    #: Function converting the value to string.
    getter = staticmethod(lambda v: v)

    def render(self):
        value = self.field.clean_value
        return dict(super(CharDisplay, self).render(),
                    value=self.getter(value),
                    should_escape=self.escape)


class FieldListWidget(Widget):

    def render(self):
        subfield = self.field.field(name='%'+self.field.input_name+'-index%')
        initial = subfield.json_data() # XXX
        return dict(super(FieldListWidget, self).render(),
                    subwidget=dict(subfield.widget.render(),
                                   initial=initial))


class FieldSetWidget(Widget):

    def render(self):
        widgets = [x.widget.render() for x in
                   self.field.fields]
        return dict(super(FieldSetWidget, self).render(),
                    widgets=widgets)



class FieldBlockWidget(FieldSetWidget):

    render_type = 'full-width'


class FileInput(Widget):

    template = 'widgets/file'

