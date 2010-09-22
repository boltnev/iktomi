# -*- coding: utf-8 -*-
'''
Module containing some predefined form converters - objects designed to
convart and validate form field's data.
'''

import re
from ..utils import weakproxy, replace_nontext
from datetime import datetime
from ..utils.odict import OrderedDict
from ..utils.dt import strftime
from ..utils import N_, M_


class NotSubmitted(Exception): pass


class SkipReadonly(NotSubmitted): pass


class NestedError(NotSubmitted): pass


class ValidationError(Exception):

    def __init__(self, message):
        Exception.__init__(self, message)

    @property
    def message(self):
        return self.args[0]

    def __str__(self):
        # This method is called by logging, we need it to avoid
        # <unprintable ValidationError object> messages.
        return self.message.encode('utf-8')


class Converter(object):
    '''
    Base converter with chaining support
    extend this class in order to get custom
    converter.

    Converting:

    :meth:`to_python` method takes value from form
    and converts it to python type

    :meth:`from_python` method takes value as python
    object and converts it to string or something
    else widget can display

    Chaining:

    Result of first converter is passed as input value
    to second. for example::

        convs.Char(max_length=2)|convs.Int()

    will be a convertor which first validates
    if string's length is 2 or less and after
    that converts it to integer

    Error messages redefinition:

    Set error_<type> parameter to your own message template, for example::

        convs.Char(min_length=5,
                   error_min_length='At least %(min_length)s characters required')`
    '''

    required = True

    #: Values are not accepted by Required validator
    error_required = N_('required field')

    def __init__(self, field=None, *args, **kwargs):
        self.field = weakproxy(field)
        self._init_kwargs = kwargs
        self.__dict__.update(kwargs)
        self.validators_and_filters = args
        self.to_python = self._check(self.to_python)

    # It is defined as read-only property to avoid setting it to True where
    # converter doesn't support it.
    @property
    def multiple(self):
        '''
        Signs if converter is multiple or not.
        Multiple converters usually accept and return collections.
        '''
        return False

    @property
    def env(self):
        return self.field.env

    def _check(self, method):
        def wrapper(value):
            if self.required and not value:
                self.error('required')
            value = method(value)
            for v in self.validators_and_filters:
                value = v(value)
            return value
        return wrapper

    def to_python(self, value):
        """ custom converters should override this """
        if value == '':
            return None
        return value

    def from_python(self, value):
        """ custom converters should override this """
        if value is None:
            value = ''
        return unicode(value)

    def __call__(self, **kwargs):
        kwargs = dict(self._init_kwargs, **kwargs)
        kwargs.setdefault('field', self.field)
        return self.__class__(**kwargs)

    def error(self, error_type, count=None,
              default=N_('unknown error')):
        '''
        Raises :class:`ValidationError <insanities.forms.convs.ValidationError>` with the
        message taken from converter's error_%(error_type) method and formatted with
        converters' attributes as arguments.

        For example::

            class Conv(Converter):
                bars = BARS

                error_foo = N_('foo')
                error_bar = M_('you need one bar', 
                               'you need %(bars) bars')

                def to_python(self, value):
                    if not footest(value):
                        self.error('foo')
                    if not bartest(value, self.bars):
                        self.error('bar', count=self.BARS)
                    return value
        '''
        message_template = getattr(self, 'error_'+error_type, default)
        message_template = self.env.gettext(message_template, count)
        message = message_template % self.__dict__
        raise ValidationError(message)

    def _assert(self, expression, error_type, count=None):
        'Shortcut for assertions of certain type'
        if not expression:
            self.error(error_type, count=None)


class validator(object):
    'Function decorator'
    def __init__(self, message):
        self.message = message
    def __call__(self, func):
        def wrapper(value):
            if not func(value):
                raise ValidationError(self.message)
            return value
        return wrapper

# Some useful validators

def limit(min_length=None, max_length=None):
    message = ''
    if min_length:
        message += 'minimal length is %d ' % min_length
    if message:
        message += ', '
    if max_length:
        message += 'maximum length is %d ' % max_length

    @validator(message)
    def wrapper(value):
        if min_length and len(value) < min_length:
            return False
        if max_length and len(value) > max_length:
            return False
        return True
    return wrapper


def int_limit(min_value=None, max_value=None):
    message = ''
    if min_value:
        message += 'minimal value is %d ' % min_value
    if message:
        message += ', '
    if max_value:
        message += 'maximum value is %d ' % max_value

    @validator(message)
    def wrapper(value):
        if min_value and value < min_value:
            return False
        if max_value and value > max_value:
            return False
        return True
    return wrapper


class Char(Converter):

    #: Regexp to match input string
    regex = None
    nontext_replacement = u'\uFFFD' # Set None to disable and empty string to
                                    # remove.
    strip=False

    error_regex = N_('field should match %(regex)s')

    def clean_value(self, value):
        '''
        Additional clean action to preprocess value before :meth:`to_python`
        method.

        Subclasses may define own clean_value method to allow additional clean
        actions like html cleanup, etc.
        '''
        # We have to clean before checking min/max length. It's done in
        # separate method to allow additional clean action in subclasses.
        if self.strip:
            value = value.strip()
        return value

    def to_python(self, value):
        # converting
        value = self.clean_value(value)
        if self.regex:
            regex = self.regex
            if isinstance(self.regex, basestring):
                regex = re.compile(self.regex, re.U)
            self._assert(regex.match(value), 'regex')
        return value

    def from_python(self, value):
        if value is None:
            return ''
        return unicode(value)


class Int(Converter):
    """
    integer converter with max and min values support
    """

    error_notvalid = N_('it is not valid integer')

    def to_python(self, value):
        if value == '':
            return None
        try:
            value = int(value)
        except ValueError:
            self.error('notvalid')
        return value

    def from_python(self, value):
        if value is None:
            return ''
        return unicode(value)


class Bool(Converter):

    def to_python(self, value):
        return bool(value)

    def from_python(self, value):
        if value:
            return 'checked'
        return ''


class DisplayOnly(Converter):

    def from_python(self, value):
        return value

    def to_python(self, value):
        raise SkipReadonly


class EnumChoice(Converter):
    '''In addition to Converter interface it must provide methods __iter__ and
    get_label.'''

    conv = Char()
    # choices: [(python_value, label), ...]
    choices = ()
    multiple = False
    error_required = N_('you must select a value')

    def from_python(self, value):
        if self.multiple:
            return [self.conv.from_python(item) for item in value or []]
        else:
            return self.conv.from_python(value)

    def _safe_to_python(self, value):
        try:
            value = self.conv.to_python(value)
        except ValidationError:
            return None
        if value not in dict(self.choices):
            return None
        return value

    def to_python(self, value):
        if value == '':
            return []
        if self.multiple:
            value = [item for item in map(self._safe_to_python, value or [])
                     if item is not None]
        else:
            value = self._safe_to_python(value)
        return value

    def __iter__(self):
        for python_value, label in self.choices:
            yield self.conv.from_python(python_value), label

    def get_label(self, value):
        return dict(self.choices).get(self.conv.to_python(value))


class DatetimeDisplay(DisplayOnly):

    format = '%d.%m.%Y, %H:%M'

    def from_python(self, value):
        if not value:
            return self.env.get_string(N_(u'is not set'))
        return value.strftime(self.format)


class BaseDatetime(Converter):

    format = None
    readable_format = None
    replacements = (('%H', 'HH'), ('%M', 'MM'), ('%d', 'DD'),
                    ('%m', 'MM'), ('%Y', 'YYYY'))
    error_wrong_format = N_('Wrong format (%(readable_format)s)')

    def __init__(self, *args, **kwargs):
        if not 'readable_format' in kwargs or 'format' in kwargs:
            replacements = self.replacements # XXX make language-dependent
            fmt = kwargs.get('format', self.format)
            for repl in replacements:
                fmt = fmt.replace(*repl)
            kwargs['readable_format'] = fmt
        Converter.__init__(self, *args, **kwargs)

    def from_python(self, value):
        if value is None:
            return ''
        # carefull to years before 1900
        return strftime(value, self.format)

    def to_python(self, value):
        if not value:
            return None
        try:
            return self.convert_datetime(value)
        except ValueError:
            self.readable_format
            raise self.error('wrong_format')
        except TypeError, e:
            raise ValidationError, e.message


class Datetime(BaseDatetime):

    format = '%d.%m.%Y, %H:%M'

    def convert_datetime(self, value):
        return datetime.strptime(value, self.format)


class Date(BaseDatetime):

    format = '%d.%m.%Y'

    def convert_datetime(self, value):
        return datetime.strptime(value, self.format).date()


class Time(BaseDatetime):

    format = '%H:%M'

    def from_python(self, value):
        if value is None:
            return ''
        # we don't care about year in time converter, so use native strftime
        return value.strftime(self.format)

    def convert_datetime(self, value):
        return datetime.strptime(value, self.format).time()


class SplitDateTime(Converter):

    def from_python(self, value):
        return {'date':value, 'time':value}

    def to_python(self, value):
        if value['date'] is None:
            return None
        res = datetime.combine(value['date'], value['time'])
        return res


class Joiner(object):

    def join(self, values):
        return values

    def split(self, value):
        return value

    def __call__(self):
        return self.__class__()


class DatetimeJoiner(Joiner):
    # XXX Two classes to split and join datetimes?
    def join(self, values):
        return datetime.combine(*values)

    def split(self, value):
        if not value:
            return None, None
        return value.date(), value.time()


class Html(Char):
    '''
    Converter for flexible cleanup of HTML document fragments.
    A subclass of :class:`Char<insanities.forms.convs.Char>`.

    Uses :class:`utils.html.Sanitizer<insanities.utils.html.Sanitizer>`
    instance to sanitize input HTML.

    Construtor collects from given kwargs all of
    :class:`Sanitizer<insanities.utils.html.Sanitizer>`
    options and passes them into Sanitizer's constructor.

    For list properties it is allowed to use :meth:`add_%s` interface::

        Html(add_allowed_elements=['span'], add_dom_callbacks=[myfunc])
    '''

    allowed_elements = frozenset(('a', 'p', 'br', 'li', 'ul', 'ol', 'hr', 'u',
                                  'i', 'b', 'blockquote', 'sub', 'sup'))
    allowed_attributes = frozenset(('href', 'src', 'alt', 'title', 'class', 'rel'))
    drop_empty_tags = frozenset(('p', 'a', 'u', 'i', 'b', 'sub', 'sup'))
    allowed_classes = {}
    #: Function returning object marked safe for template engine.
    #: For example: jinja Markup object
    Markup = lambda s, x: x

    def _load_arg(self, kwargs, opt):
        if hasattr(self, opt):
            kwargs.setdefault(opt, getattr(self, opt))

    def __init__(self, **kwargs):
        from ..utils.html import PROPERTIES, LIST_PROPERTIES

        for opt in PROPERTIES:
            if not opt in kwargs:
                # passed throught kwargs set is stronger then stored in class
                # add_%  
                self._load_arg(kwargs, 'add_' + opt)
            self._load_arg(kwargs, opt)

        for opt in LIST_PROPERTIES:
            add_key = 'add_' + opt
            if add_key in kwargs:
                kwargs[opt] = set(kwargs.get(opt, LIST_PROPERTIES[opt]))
                kwargs[opt].update(kwargs.pop(add_key))

        super(Html, self).__init__(**kwargs)

    def clean_value(self, value):
        from ..utils.html import ParseError, Sanitizer

        value = super(Html, self).clean_value(value)
        sanitizer = Sanitizer(**self._init_kwargs)
        try:
            clean = sanitizer.sanitize(value)
        except ParseError:
            raise ValidationError, u'not valid html'
        else:
            return self.Markup(clean)

    @property
    def tags(self):
        return self.allowed_elements
    @property
    def attrs(self):
        return self.allowed_attributes


class List(Converter):

    filter = None

    def from_python(self, value):
        result = OrderedDict()
        for index, item in enumerate(value):
            result[str(index+1)] = item
        return result

    def to_python(self, value):
        items = value.values()
        if self.filter is not None:
            items = filter(self.filter, items)
        return items
