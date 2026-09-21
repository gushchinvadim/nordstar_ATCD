# landing/models.py
from django.db import models
from training.models import Module  # Связь с модулями обучения


class NewsItem(models.Model):
    """Новости АУЦ"""
    title = models.CharField("Заголовок", max_length=200)
    slug = models.SlugField("URL-идентификатор", unique=True)
    content = models.TextField("Содержание")
    image = models.ImageField("Изображение", upload_to='landing/news/', blank=True, null=True)
    published_at = models.DateTimeField("Дата публикации", auto_now_add=True)
    is_active = models.BooleanField("Опубликовано", default=True)

    class Meta:
        verbose_name = "Новость"
        verbose_name_plural = "Новости"
        ordering = ['-published_at']

    def __str__(self):
        return self.title


class CourseHighlight(models.Model):
    """Рекомендуемые курсы на лендинге"""
    module = models.ForeignKey(Module, on_delete=models.CASCADE, verbose_name="Модуль обучения")
    description = models.TextField("Краткое описание", max_length=500)
    order = models.PositiveIntegerField("Порядок отображения", default=0)
    is_featured = models.BooleanField("Рекомендуемый", default=False)

    class Meta:
        verbose_name = "Рекомендуемый курс"
        verbose_name_plural = "Рекомендуемые курсы"
        ordering = ['order']

    def __str__(self):
        return f"{self.module.title} ({'⭐' if self.is_featured else 'обычный'})"


class StatBlock(models.Model):
    """Блоки статистики на лендинге"""
    title = models.CharField("Заголовок", max_length=100)
    value = models.CharField("Значение", max_length=50, help_text="Например: 1500+")
    description = models.CharField("Описание", max_length=200)
    icon = models.CharField("Иконка (emoji)", max_length=10, default="📊")
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Блок статистики"
        verbose_name_plural = "Блоки статистики"
        ordering = ['order']

    def __str__(self):
        return f"{self.icon} {self.title}: {self.value}"


class AboutSection(models.Model):
    """Секция 'О компании'"""
    title = models.CharField("Заголовок", max_length=200)
    content = models.TextField("Текст")
    image = models.ImageField("Изображение", upload_to='landing/about/', blank=True, null=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Секция 'О компании'"
        verbose_name_plural = "Секции 'О компании'"
        ordering = ['order']

    def __str__(self):
        return self.title


class Partner(models.Model):
    """Партнеры/клиенты АУЦ"""
    name = models.CharField("Название", max_length=200)
    logo = models.ImageField("Логотип", upload_to='landing/partners/')
    website = models.URLField("Сайт", blank=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Партнер"
        verbose_name_plural = "Партнеры"
        ordering = ['order']

    def __str__(self):
        return self.name