_mixin_cache = {}

def has_method_in_mro(cls, name: str) -> bool:
    """Check if any class in the MRO explicitly defines a method with this name."""
    return any(name in c.__dict__ for c in cls.__mro__)

def ensure_mixin(parser_cls, mixin):
    """
    Return a new class where `mixin` is placed before parser_cls in the MRO.
    - Idempotent: if the mixin is already present, return parser_cls.
    - Cached: reuse the same mixed class if already created.
    - Safe: only apply if the target method exists somewhere in the MRO.
    """
    # If mixin already present -> nothing to do
    if mixin in parser_cls.__mro__:
        return parser_cls

    # Only mixin if the method exists
    if not has_method_in_mro(parser_cls, "_add_multiinstance_task"):
        return parser_cls

    key = (parser_cls, mixin)
    if key in _mixin_cache:
        return _mixin_cache[key]

    # Dynamically create a new subclass
    mixed = type(f"{parser_cls.__name__}With{mixin.__name__}", (mixin, parser_cls), {})
    _mixin_cache[key] = mixed
    return mixed