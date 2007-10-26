======================================
Separating Concerns Using Object Roles
======================================

(NEW in version 0.6: the``Registry`` base class, and the
``ClassRole.for_frame()`` classmethod.)

In any sufficiently-sized application or framework, it's common to end up
lumping a lot of different concerns into the same class.  For example, you
may have business logic, persistence code, and UI all jammed into a single
class.  Attribute and method names for all sorts of different operations get
shoved into a single namespace -- even when using mixin classes.

Separating concerns into different objects, however, makes it easier to write
reusable and separately-testable components.  The ObjectRoles package
(``peak.util.roles``) lets you manage concerns using ``Role`` classes.

``Role`` classes are like dynamic mixins, but with their own private attribute
and method namespaces.  A concern implemented using roles can be added at
runtime to any object that either has a writable ``__dict__`` attribute, or
is weak-referenceable.

``Role`` classes are also like adapters, but rather than creating a new
instance each time you ask for one, an existing instance is returned if
possible.  In this way, roles can keep track of ongoing state.  For example,
a ``Persistence`` role might keep track of whether its subject has been saved
to disk yet::

    >>> from peak.util.roles import Role

    >>> class Persistence(Role):
    ...     saved = True
    ...     def changed(self):
    ...         self.saved = False
    ...     def save_if_needed(self):
    ...         if not self.saved:
    ...             print "saving"
    ...             self.saved = True

    >>> class Thing: pass
    >>> aThing = Thing()

    >>> Persistence(aThing).saved
    True
    >>> Persistence(aThing).changed()
    >>> Persistence(aThing).saved
    False
    >>> Persistence(aThing).save_if_needed()
    saving
    >>> Persistence(aThing).save_if_needed() # no action taken

This makes it easy for us to, for example, write a loop that saves a bunch of
objects, because we don't need to concern ourselves with initializing the
state of the persistence role.  A class doesn't need to inherit from a special
base in order to be able to have this state tracked, and it doesn't need to
know *how* to initialize it, either.

Of course, in the case of persistence, a class does need to know *when* to call
the persistence methods, to indicate changedness and to request saving.
However, a library providing such a role can also provide decorators and other
tools to make this easier, while still remaining largely independent of the
objects involved.

Indeed, the ObjectRoles library was actually created to make it easier to
implement functionality using function or method decorators.  For example, one
can create a ``@synchronized`` decorator that safely locks an object -- see
the example below under `Threading Concerns`_.

In summary, the ObjectRoles library provides you with a basic form of AOP,
that lets you attach (or "introduce", in AspectJ terminology) additional
attributes and methods to an object, using a private namespace.  (If you also
want to do AspectJ-style "advice", the PEAK-Rules package can be used to do
"before", "after", and "around" advice in combination with ObjectRoles.)


.. contents:: **Table of Contents**


Basic API
---------

If you need to, you can query for the existence of a Role::

    >>> Persistence.exists_for(aThing)
    True

And by default, it won't exist::

    >>> anotherThing = Thing()
    >>> Persistence.exists_for(anotherThing)
    False

Until you refer to it directly, e.g.::

    >>> Persistence(aThing) is Persistence(anotherThing)
    False

At which point it will of course exist::

    >>> Persistence.exists_for(anotherThing)
    True

And maintain its state, linked to its subject::

    >>> Persistence(anotherThing) is Persistence(anotherThing)
    True

Until/unless you delete it (or its subject is garbage collected)::

    >>> Persistence.delete_from(anotherThing)
    >>> Persistence.exists_for(anotherThing)
    False


Role Keys and Instances
-----------------------

Roles are stored either in their subject's ``__dict__``, or if it does not have
one (or is a new-style class with a read-only ``__dict__``), they are stored in
a special dictionary linked to the subject via a weak reference.

By default, the dictionary key is the role class, so there is exactly one role
instance per subject::

    >>> aThing.__dict__
    {<class 'Persistence'>: <Persistence object at...>}

But in some cases, you may wish to have more than one instance of a given role
class for a subject.  (For example, PEAK-Rules uses roles to represent indexes
on different expressions contained within rules.)  For this purpose, you can
redefine your Role's ``__init__`` method to accept additional arguments besides
its subject.  The additional arguments become part of the key that instances
are stored under, such that more than one role instance can exist for a given
object::

    >>> class Index(Role, dict):
    ...     def __init__(self, subject, expression):
    ...         self.expression = expression

    >>> something = Thing()
    >>> Index(something, "x>y")["a"] = "b"
    >>> dir(something)
    ['__doc__', '__module__', (<class 'Index'>, 'x>y')]

    >>> "a" in Index(something, "z<22")
    False

    >>> Index(something, "x>y")
    {'a': 'b'}

    >>> Index(something, "x>y").expression
    'x>y'

    >>> dir(something)
    ['__doc__', '__module__', (<class 'Index'>, 'x>y'), (<class 'Index'>, 'z<22')]

    >>> Index.exists_for(something, 'x>y')
    True

    >>> Index.exists_for(anotherThing, 'q==42')
    False

By default, a role class' key is either the class by itself, or a tuple
containing the class, followed by any arguments that appeared in the
constructor call after the role's subject.  However, you can redefine the
``role_key()`` classmethod in your subclass, and change it to do something
different.  For example, you could make different role classes generate
overlapping keys, or you could use attributes of the arguments to generate the
key.  You could even generate a string key, to cause the role to be attached
as an attribute!::

    >>> class Leech(Role):
    ...     def role_key(cls):
    ...         return "__leech__"
    ...     role_key = classmethod(role_key)

    >>> something = Thing()

    >>> Leech(something) is something.__leech__
    True

The ``role_key`` method only receives the arguments that appear *after* the
subject in the constructor call.  So, in the case above, it receives no
arguments.  Had we called it with additional arguments, we'd have gotten an
error::

    >>> Leech(something, 42)
    Traceback (most recent call last):
      ...
    TypeError: role_key() takes exactly 1 argument (2 given)

Naturally, your ``role_key()`` and ``__init__()`` (and/or ``__new__()``)
methods should also agree on how many arguments there can be, and what they
mean!

In general, you should include your role class (or some role class) as part of
your key, so as to make collisions with other people's role classes impossible.
Keys should also be designed for thread-safety, where applicable.  (See
the section below on `Threading Concerns`_ for more details.)


Role Storage and Garbage Collection
-----------------------------------

By the way, the approach above of using an string as a role key won't always
make the role into an attribute of the subject!  If an object doesn't have a
``__dict__``, or that ``__dict__`` isn't writable (as in the case of new-style
classes), then the role is stored in a weakly-keyed dictionary, maintained
elsewhere::

    >>> class NoDict(object):
    ...     __slots__ = '__weakref__'

    >>> dictless = NoDict()

    >>> Leech(dictless)
    <Leech object at ...>

    >>> dictless.__leech__
    Traceback (most recent call last):
      ...
    AttributeError: 'NoDict' object has no attribute '__leech__'

Of course, if an object doesn't have a dictionary *and* isn't
weak-referenceable, there's simply no way to store a role for it::

    >>> ob = object()
    >>> Leech(ob)
    Traceback (most recent call last):
      ...
    TypeError: cannot create weak reference to 'object' object

However, there is a ``roledict_for()`` function in the ``peak.util.roles``
module that you can extend using PEAK-Rules advice.  Once you add a method to
support a type that otherwise can't be used with roles, you should be able to
use any and all kinds of role objects with that type.  (Assuming, of course,
that you can implement a suitable storage mechanism!)

Finally, a few words regarding garbage collection.  If you don't want to create
a reference cycle, don't store a reference to your subject in your role.  Even
though the ``__init__`` and ``__new__`` messages get the subject passed in, you
are not under any obligation to *store* the subject, and often won't need to.
Usually, the code that is accessing the role knows what subject is in use, and
can pass the subject to the role's methods if needed.  It's rare that the
role really needs to keep a reference to the subject past the ``__new__()`` and
``__init__()`` calls.

Role instances will usually be garbage collected at the same time as their
subject, unless there is some other reference to them.  If they keep a
reference to their subject, their garbage collection may be delayed until
Python's cycle collector is run.  But if they don't keep a reference, they will
usually be deleted as soon as the subject is::

    >>> def deleting(r):
    ...     print "deleting", r

    >>> from weakref import ref

    >>> r = ref(Leech(something), deleting)
    >>> del something
    deleting <weakref at ...; dead>

(Roles that are stored outside the instance dictionary of their subject,
however, may take slightly longer, as Python processes weak reference
callbacks.)

It is also *not* recommended that you have ``__del__`` methods on your role
objects, especially if you keep a reference to your subject.  In such a case,
garbage collection may become impossible, and both the role and its subject
would "leak" (i.e., take up memory forever without being recoverable).


Class Roles
-----------

Sometimes, it's useful to attach roles to classes instead of instances.  You
could use normal ``Role`` classes, of course, as they work just fine with both
classic classes and new-style types -- even built-ins::

    >>> Persistence.exists_for(int)
    False

    >>> Persistence(int) is Persistence(int)
    True

    >>> Persistence.exists_for(int)
    True

    >>> class X: pass

    >>> Persistence.exists_for(X)
    False

    >>> Persistence(X) is Persistence(X)
    True

    >>> Persistence.exists_for(X)
    True

But, sometimes you have roles that are specifically intended for adding
metadata to classes -- perhaps by way of class or method decorators.  In such
a case, you need a way to access the role *before* its subject even exists!

The ``ClassRole`` base class provides a mechanism for this.  It adds an extra
classmethod, ``for_enclosing_class()``, that you can use to access the role
for the class that is currently being defined in the scope that invoked the
caller.  For example, suppose we want to have a method decorator that adds
the method to some class-level registry::

    >>> from peak.util.roles import ClassRole

    >>> class SpecialMethodRegistry(ClassRole):
    ...     def __init__(self, subject):
    ...         self.special_methods = {}
    ...         super(SpecialMethodRegistry, self).__init__(subject)

    >>> def specialmethod(func):
    ...     smr = SpecialMethodRegistry.for_enclosing_class()
    ...     smr.special_methods[func.__name__] = func
    ...     return func

    >>> class Demo:
    ...     def dummy(self, foo):
    ...         pass
    ...     dummy = specialmethod(dummy)

    >>> SpecialMethodRegistry(Demo).special_methods
    {'dummy': <function dummy at ...>}

    >>> class Demo2(object):
    ...     def dummy(self, foo):
    ...         pass
    ...     dummy = specialmethod(dummy)

    >>> SpecialMethodRegistry(Demo2).special_methods
    {'dummy': <function dummy at ...>}

You can of course use the usual role API for class roles::

    >>> SpecialMethodRegistry.exists_for(int)
    False

    >>> SpecialMethodRegistry(int).special_methods['x'] = 123

    >>> SpecialMethodRegistry.exists_for(int)
    True

Except that you cannot explicitly delete them, they must be garbage collected
naturally::

    >>> SpecialMethodRegistry.delete_from(Demo)
    Traceback (most recent call last):
      ...
    TypeError: ClassRoles cannot be deleted


Delayed Initialization
~~~~~~~~~~~~~~~~~~~~~~

When a class role is initialized, the class may not exist yet.  In this case,
``None`` is passed as the first argument to the ``__new__`` and ``__init__``
methods.  You must be able to handle this case correctly, if your role will
be accessed inside a class definition with ``for_enclosing_class()``.

You can, however, define a ``created_for()`` instance method that will be
called as soon as the actual class is available.  It is also called by the
default ``__init__`` method, if the role is initially created for a class that
already exists.  Either way, the ``created_for()`` method should be called at
most once for any given role instance.  For example::

    >>> class SpecialMethodRegistry(ClassRole):
    ...     def __init__(self, subject):
    ...         print "init called for", subject
    ...         self.special_methods = {}
    ...         super(SpecialMethodRegistry, self).__init__(subject)
    ...
    ...     def created_for(self, cls):
    ...         print "created for", cls.__name__

    >>> class Demo:
    ...     def dummy(self, foo):
    ...         pass
    ...     dummy = specialmethod(dummy)
    init called for None
    created for Demo

Above, ``__init__`` was called with ``None`` since the type didn't exist yet.
However, accessing the role for an existing type (that doesn't have the role
yet) will call ``__init__`` with the type, and the default implementation of
``ClassRole.__init__`` will also call ``created_for()`` for us, when it sees
the subject is not ``None``::

    >>> SpecialMethodRegistry(float)
    init called for <type 'float'>
    created for float
    <SpecialMethodRegistry object at ...>

    >>> SpecialMethodRegistry(float)    # created_for doesn't get called again
    <SpecialMethodRegistry object at ...>

One of the most useful features of having this ``created_for()`` method is
that it allows you to set up class-level metadata that involves inherited
settings from base classes.  In ``created_for()``, you have access to the
class' ``__bases__`` and or ``__mro__``, and you can just ask for an instance
of the same role for those base classes, then incorporate their data into your
own instance as appropriate.  You are guaranteed that any such roles you access
will already be initialized, including having their ``created_for()`` method
called.

Since this works recursively, and because class roles can be attached even to
built-in types like ``object``, the work of creating a correct class metadata
registry is immensely simplified, compared to having to special case such base
classes, check for bases where no metadata was added or defined, etc.

Instead, classes that didn't define any metadata will just have a role instance
containing whatever was setup by your role's ``__init__()`` method, plus
whatever additional data was added by its ``created_for()`` method.

Thus, metadata accumulation using class roles can actually be simpler than
doing the same things with metaclasses, since metaclasses can't be
retroactively added to existing classes.  Of course, class roles can't entirely
replace metaclasses or base class mixins, but for the things they *can* do,
they are much easier to implement correctly.


Keys, Decoration, and ``for_enclosing_class()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Class roles can have role keys, just like regular roles, and they're
implemented in the same way.  And, you can pass the extra arguments as
positional arguments to ``for_enclosing_class()``.  For example::

    >>> class Index(ClassRole):
    ...     def __init__(self, subject, expr):
    ...         self.expr = expr
    ...         self.funcs = []
    ...         super(Index, self).__init__(subject)

    >>> def indexedmethod(expr):
    ...     def decorate(func):
    ...         Index.for_enclosing_class(expr).funcs.append(func)
    ...         return func
    ...     return decorate

    >>> class Demo:
    ...     def dummy(self, foo):
    ...         pass
    ...     dummy = indexedmethod("x*y")(dummy)

    >>> Index(Demo, "x*y").funcs
    [<function dummy at ...>]

    >>> Index(Demo, "y+z").funcs
    []

Note, by the way, that you do not need to use a function decorator to add
metadata to a class.  You just need to be calling ``for_enclosing_class()``
in a function called directly from the class body::

    >>> def special_methods(**kw):
    ...     smr = SpecialMethodRegistry.for_enclosing_class()
    ...     smr.special_methods.update(kw)

    >>> class Demo:
    ...     special_methods(x=23, y=55)
    init called for None
    created for Demo

    >>> SpecialMethodRegistry(Demo).special_methods
    {'y': 55, 'x': 23}

By default, the ``for_enclosing_class()`` method assumes is it being called by
a function that is being called directly from the class suite, such as a
method decorator, or a standalone function call as shown above.  But if you
make a call from somewhere else, such as outside a class statement, you will
get an error::

    >>> special_methods(z=42)
    Traceback (most recent call last):
      ...
    SyntaxError: Class decorators may only be used inside a class statement

Similarly, if you have a function that calls ``for_enclosing_class()``, but
then you call that function from another function, it will still fail::

    >>> def sm(**kw):
    ...     special_methods(**kw)

    >>> class Demo:
    ...     sm(x=23, y=55)
    Traceback (most recent call last):
      ...
    SyntaxError: Class decorators may only be used inside a class statement

This is because ``for_enclosing_class()`` assumes the class is being defined
two stack levels above its frame.  You can change this assumption, however,
by using the ``level`` keyword argument::

    >>> def special_methods(level=2, **kw):
    ...     smr = SpecialMethodRegistry.for_enclosing_class(level=level)
    ...     smr.special_methods.update(kw)

    >>> def sm(**kw):
    ...     special_methods(level=3, **kw)

    >>> class Demo:
    ...     sm(x=23)
    ...     special_methods(y=55)
    init called for None
    created for Demo

    >>> SpecialMethodRegistry(Demo).special_methods
    {'y': 55, 'x': 23}

Alternately, you can pass a specific Python frame object via the ``frame``
keyword argument to ``for_enclosing_class()``, or use the ``for_frame()``
classmethod instead.  ``for_frame()`` takes a Python stack frame, followed by
any extra positional arguments needed to create the key.


Class Registries (NEW in version 0.6)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For many of common class role use cases, you just want a dictionary-like object
with "inheritance" for the values in base classes.  The ``Registry`` base class
provides this behavior, by subclassing ``ClassRole`` and the Python ``dict``
builtin type, to create a class role that's also a dictionary.  It then
overrides the ``created_for()`` method to automatically populate itself with
any inherited values from base classes.

Let's define a ``MethodGoodness`` registry that will store a "goodness"
rating for methods::

    >>> from peak.util.roles import Registry

    >>> class MethodGoodness(Registry):
    ...     """Dictionary of method goodness"""

    >>> def goodness(value):
    ...     def decorate(func):
    ...         MethodGoodness.for_enclosing_class()[func.__name__]=value
    ...         return func
    ...     return decorate

    >>> class Demo(object):
    ...     def aMethod(self, foo):
    ...         pass
    ...     aMethod = goodness(17)(aMethod)
    ...     def another_method(whinge, spam):
    ...         woohoo
    ...     another_method = goodness(-99)(another_method)

    >>> MethodGoodness(Demo)
    {'aMethod': 17, 'another_method': -99}

So far, so good.  Let's see what happens with a subclass::    

    >>> class Demo2(Demo):
    ...     def another_method(self, fixed):
    ...         pass
    ...     another_method = goodness(42)(another_method)

    >>> MethodGoodness(Demo2)
    {'another_method': 42, 'aMethod': 17}

Values set in base class registries are automatically added to the current
class' registry of the same type and key, if the current class doesn't have
an entry defined.  Python's new-style method resolution order is used to
determine the precedence of inherited attributes.  (For classic classes, a
temporary new-style class is created that inherits from the classic class, in
order to determine the resolution order, then discarded.)

Once the class in question has been created, the registry gets an extra
attribute, ``defined_in_class``, which is a dictionary listing the entries that
were actually defined in the corresponding class, e.g.::

    >>> MethodGoodness(Demo).defined_in_class
    {'aMethod': 17, 'another_method': -99}
    
    >>> MethodGoodness(Demo2).defined_in_class
    {'another_method': 42}

As you can see, this second dictionary contains only the values registered in
that class, and not any inherited values.

Finally, note that ``Registry`` objects have one additional method that can
be useful to call from a decorator: ``set(key, value)``.  This method will
raise an error if a different value already exists for the given key, and is
useful for catching errors in class definitions, e.g.:

    >>> def goodness(value):
    ...     def decorate(func):
    ...         MethodGoodness.for_enclosing_class().set(func.__name__, value)
    ...         return func
    ...     return decorate

    >>> class Demo3(object):
    ...     def aMethod(self, foo):
    ...         pass
    ...     aMethod = goodness(17)(aMethod)
    ...     def aMethod(self, foo):
    ...         pass
    ...     aMethod = goodness(27)(aMethod)
    Traceback (most recent call last):
      ...
    ValueError: MethodGoodness['aMethod'] already contains 17; can't set to 27


Threading Concerns
------------------

Role lookup and creation is thread-safe (i.e. race-condition free), so long as
the role key contains no objects with ``__hash__`` or ``__equals__`` methods
written in Python (as opposed to C).  So, unkeyed roles, or roles whose keys
consist only of instances of built-in types (recursively, in the case of
tuples) or types that inherit their ``__hash__`` or ``__equals__`` methods from
built-in types, can be initialized in a thread-safe manner.

This does *not* mean, however, that two or more role instances can't be created
for the same subject at the same time!  Code in a role class' ``__new__`` or
``__init__`` methods **must not** assume that it will in fact be the only role
instance attached to its subject, if you wish the code to be thread-safe.

This is because the Role access machinery allows multiple threads to *create*
a role instance at the same time, but only one of those objects will *win* the
race to become "the" role instance, and no thread can know in advance whether
it will win.  Thus, if you wish your Role instances to do something *to* their
constructor arguments at initialization time, you must either give up on your
role being thread-safe, or use some other locking mechanism.

Of course, role initialization is only one small part of the overall thread-
safety puzzle.  Unless your role exists only to compute some immutable metadata
about its subject, the rest of your role's methods need to be thread-safe also.

One way to do that, is to use a ``@synchronized`` decorator, combined with a
``Locking`` role::

    >>> class Locking(Role):
    ...     def __init__(self, subject):
    ...         from threading import RLock
    ...         self.lock = RLock()
    ...     def acquire(self):
    ...         print "acquiring"
    ...         self.lock.acquire()
    ...     def release(self):
    ...         self.lock.release()
    ...         print "released"

    >>> def synchronized(func):
    ...     def wrapper(self, *__args,**__kw):
    ...         Locking(self).acquire()
    ...         try:
    ...             func(self, *__args,**__kw)
    ...         finally:
    ...             Locking(self).release()
    ...
    ...     from peak.util.decorators import rewrap
    ...     return rewrap(func, wrapper)

    >>> class AnotherThing:
    ...     def ping(self):
    ...         print "ping"
    ...     ping = synchronized(ping)

    >>> AnotherThing().ping()
    acquiring
    ping
    released

If the ``Locking()`` role constructor were not thread-safe, this decorator would
not be able to do its job correctly, because two threads accessing an object
that didn't *have* the role yet, could end up locking two different locks, and
proceeding to run the supposedly-"synchronized" method at the same time!

In general, thread-safety is harder than it looks.  But at least you don't have
to worry about this one tiny part of correctly implementing it.

Of course, synchronized methods will be slower than normal methods, which is
why ObjectRoles doesn't do anything besides that one small part of the thread-
safety puzzle, to avoid penalizing non-threaded code.  As the PEAK motto says,
STASCTAP! (Simple Things Are Simple, Complex Things Are Possible.)


Mailing List
------------

Questions, discussion, and bug reports for this software should be directed to
the PEAK mailing list; see http://www.eby-sarna.com/mailman/listinfo/PEAK/
for details.

