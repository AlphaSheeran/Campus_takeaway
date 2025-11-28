from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """通过键获取字典值的自定义过滤器"""
    return dictionary.get(key)
