from jsonschema.exceptions import ValidationError
from jsonschema.validators import Draft6Validator, extend

from test_suite import bindings


### TYPES ###


def is_code(checker, instance):
    return isinstance(instance, str)


def is_coding(checker, instance):
    allowed_fields = {'system', 'version', 'code', 'display', 'userSelected'}
    return (
        isinstance(instance, dict)
        and not (instance.keys() - allowed_fields)
    )


def is_codeable_concept(checker, instance):
    allowed_fields = {'coding', 'text'}
    codings = instance.get('coding', list())
    return (
        isinstance(instance, dict)
        and not (instance.keys() - allowed_fields)
        and isinstance(codings, list)
        and all(is_coding(checker, coding) for coding in codings)
    )


TYPE_CHECKER = (
    Draft6Validator.TYPE_CHECKER
    .redefine('code', is_code)
    .redefine('coding', is_coding)
    .redefine('codeableConcept', is_codeable_concept)
)


def make_reference_type(fetcher):
    def is_reference(checker, instance):
        allowed_fields = {'reference', 'display'}
        reference = instance.get('reference')
        return (
            isinstance(instance, dict)
            and not (instance.keys() - allowed_fields)
            and reference  # technically this is not required, hmm...
            and fetcher(reference)
        )

    return is_reference


### VALIDATORS ###


def binding(validator, binding, instance, schema):
    if validator.is_type(instance, 'code'):
        func = bindings.validate_code
    elif validator.is_type(instance, 'coding'):
        func = bindings.validate_coding
    elif validator.is_type(instance, 'codeableConcept'):
        func = bindings.validate_codeable_concept
    else:
        return

    value_set = binding.get('valueSet')
    strength = binding.get('strength')
    if value_set and strength:
        try:
            func(instance, value_set, strength)
        except bindings.BindingError as error:
            yield ValidationError(str(error))


def profiles(validator, profiles, instance, schema):
    for name, profile in profiles.items():
        # TODO: version check, use case check?
        schema = profile.get('schema')
        if not schema:
            return

        for error in validator.descend(instance, schema):
            # TODO: rewrap error
            yield error


VALIDATORS = {'binding': binding, 'profiles': profiles}


def get_s4s_validator(fetcher):
    type_checker = TYPE_CHECKER.redefine(
        'reference', make_reference_type(fetcher)
    )
    return extend(
        Draft6Validator, validators=VALIDATORS, type_checker=type_checker
    )
