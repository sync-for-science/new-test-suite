REQUIRED = 'required'
EXTENSIBLE = 'extensible'
PREFERRED = 'preferred'
EXAMPLE = 'example'


class BindingError(Exception):
    pass


# TODO: handle extensible/preferred?


def validate_code(instance, value_set, strength):
    if strength == REQUIRED:
        if not value_set.contains(code=instance):
            raise BindingError(f'"{instance}" is not in the "{value_set.name}" value set')


def validate_coding(instance, value_set, strength):
    system = instance.get('system')
    code = instance.get('code')
    if strength == REQUIRED:
        if not value_set.contains(system=system, code=code):
            raise BindingError(f'"{code}" in system "{system}" is not in the "{value_set.name}" value set')


def validate_codeable_concept(instance, value_set, strength):
    codings = instance.get('coding', list())
    passing = False
    for coding in codings:
        try:
            validate_coding(coding, value_set, strength)
            passing = True
        except BindingError:
            pass

    if not passing:
        if strength == REQUIRED:
            raise BindingError(f'None of the codes in the "coding" array are in the "{value_set.name}" value set')
