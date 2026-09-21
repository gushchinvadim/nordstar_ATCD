from django import template

register = template.Library()

@register.filter(name='dict_get')
def dict_get(dictionary, key):
    """Безопасное получение значения из словаря по ключу в шаблоне Django"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None