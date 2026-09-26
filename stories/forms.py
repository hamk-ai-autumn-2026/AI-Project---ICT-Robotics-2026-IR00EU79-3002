from django import forms

from .models import Story


class StoryForm(forms.ModelForm):
    class Meta:
        model = Story
        fields = [
            "child_name",
            "child_gender",
            "child_appearance",
            "favorite_theme",
            "reading_level",
            "moral_lesson",
        ]
        labels = {
            "child_name": "Child's name",
            "child_gender": "Child's gender",
            "child_appearance": "Appearance",
            "favorite_theme": "Favorite animal or theme",
            "reading_level": "Reading level",
            "moral_lesson": "Moral or lesson to teach",
        }
        widgets = {
            "child_appearance": forms.Textarea(
                attrs={"rows": 2, "placeholder": "e.g. curly black hair, brown eyes, wears glasses"}
            ),
            "child_name": forms.TextInput(attrs={"placeholder": "e.g. Amara"}),
            "favorite_theme": forms.TextInput(attrs={"placeholder": "e.g. dinosaurs, foxes, outer space"}),
            "moral_lesson": forms.TextInput(attrs={"placeholder": "e.g. sharing is caring"}),
        }
