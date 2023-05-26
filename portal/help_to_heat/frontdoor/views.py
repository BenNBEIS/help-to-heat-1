import uuid

from django.shortcuts import redirect, render
from django.urls import reverse
from help_to_heat import utils

from . import interface, schemas
from help_to_heat.portal import models as portal_models

page_map = {}


page_compulsory_field_map = {
    "country": ("country",),
    "own-property": ("own_property",),
    "address": ("address_line_1", "postcode"),
    "address-manual": ("address_line_1", "town_or_city", "postcode"),
    "epc-found": ("accept_suggested_epc",),
    "council-tax-band": ("council_tax_band",),
    "benefits": ("benefits",),
    "household-income": ("household_income",),
    "property-type": ("property_type",),
    "number-of-bedrooms": ("number_of_bedrooms",),
    "wall-type": ("wall_type",),
    "wall-insulation": ("wall_insulation",),
    "loft": ("loft",),
    "loft-access": ("loft_access",),
    "supplier": ("supplier",),
    "contact-details": ("first_name", "last_name", "contact_number", "email"),
    "confirm-and-submit": ("permission",),
}


def register_page(name):
    def _inner(func):
        page_map[name] = func
        return func

    return _inner


def homepage_view(request):
    session_id = uuid.uuid4()
    next_url = reverse("frontdoor:page", kwargs=dict(session_id=session_id, page_name="country"))
    context = {
        "next_url": next_url,
    }
    return render(request, template_name="frontdoor/homepage.html", context=context)


def get_prev_next_page_name(page_name):
    if page_name in schemas.page_prev_next_map:
        prev_page_name = schemas.page_prev_next_map[page_name]["prev"]
        next_page_name = schemas.page_prev_next_map[page_name]["next"]
    else:
        assert page_name in schemas.pages
        page_index = schemas.pages.index(page_name)
        if page_index == 0:
            prev_page_name = "homepage"
        else:
            prev_page_name = schemas.pages[page_index - 1]
        if page_index + 1 == len(schemas.pages):
            next_page_name = None
        else:
            next_page_name = schemas.pages[page_index + 1]
    return prev_page_name, next_page_name


def get_prev_next_urls(session_id, page_name):
    prev_page_name, next_page_name = get_prev_next_page_name(page_name)
    if page_name == "benefits":
        accepted_ecp_suggestion = interface.api.session.get_answer(session_id, "epc-found")["accept_suggested_epc"]
        if accepted_ecp_suggestion:
            prev_page_name = "epc-found"
        else:
            prev_page_name = "council-tax-band"
    if page_name == "council-tax-band":
        prev_page_name = "address"
    if prev_page_name == "homepage":
        prev_page_url = reverse("frontdoor:homepage")
    else:
        prev_page_url = prev_page_name and reverse(
            "frontdoor:page", kwargs=dict(session_id=session_id, page_name=prev_page_name)
        )
    prev_page_url = prev_page_name and reverse(
        "frontdoor:page", kwargs=dict(session_id=session_id, page_name=prev_page_name)
    )
    next_page_url = next_page_name and reverse(
        "frontdoor:page", kwargs=dict(session_id=session_id, page_name=next_page_name)
    )
    return prev_page_url, next_page_url


class PageView(utils.MethodDispatcher):
    def get(self, request, session_id, page_name, errors=None, is_change_page=False, override_prev_page_url=None):
        if not errors:
            errors = {}
        if override_prev_page_url is not None:
            _, next_page_url = get_prev_next_urls(session_id, page_name)
            prev_page_url = override_prev_page_url
        elif is_change_page:
            assert page_name in schemas.change_page_lookup
            prev_page_name = schemas.change_page_lookup[page_name]
            prev_page_url = reverse("frontdoor:page", kwargs=dict(session_id=session_id, page_name=prev_page_name))
            next_page_url = None
        else:
            prev_page_url, next_page_url = get_prev_next_urls(session_id, page_name)
        data = interface.api.session.get_answer(session_id, page_name)
        extra_context = self.get_context(request=request, session_id=session_id, page_name=page_name, data=data)
        context = {
            "data": data,
            "session_id": session_id,
            "errors": errors,
            "prev_url": prev_page_url,
            "next_url": next_page_url,
            **extra_context,
        }
        return render(request, template_name=f"frontdoor/{page_name}.html", context=context)

    def post(self, request, session_id, page_name, is_change_page=False):
        data = request.POST.dict()
        errors = self.validate(request, session_id, page_name, data, is_change_page)
        if errors:
            return self.get(request, session_id, page_name, errors=errors, is_change_page=is_change_page)
        else:
            data = self.save_data(request, session_id, page_name)
            return self.handle_post(request, session_id, page_name, data, is_change_page)

    def save_data(self, request, session_id, page_name, *args, **kwargs):
        data = interface.api.session.save_answer(session_id, page_name, request.POST.dict())
        return data

    def get_context(self, request, session_id, page_name, data):
        return {}

    def handle_post(self, request, session_id, page_name, data, is_change_page):
        if is_change_page:
            assert page_name in schemas.change_page_lookup
            next_page_name = schemas.change_page_lookup[page_name]
        else:
            next_page_name = schemas.pages[schemas.pages.index(page_name) + 1]
        return redirect("frontdoor:page", session_id=session_id, page_name=next_page_name)

    def validate(self, request, session_id, page_name, data, is_change_page):
        fields = page_compulsory_field_map.get(page_name, ())
        missing_fields = tuple(field for field in fields if not data.get(field))
        errors = {field: "Please answer this question" for field in missing_fields}
        return errors


@register_page("country")
class CountryView(PageView):
    def get(self, request, session_id, page_name, errors=None, is_change_page=False, override_prev_page_url=None):
        override_prev_page_url = reverse("frontdoor:homepage")
        return super().get(request, session_id, page_name, errors, is_change_page, override_prev_page_url)

    def get_context(self, *args, **kwargs):
        return {"country_options": schemas.country_options}

    def handle_post(self, request, session_id, page_name, data, is_change_page):
        if data["country"] == "Northern Ireland":
            return redirect("frontdoor:page", session_id=session_id, page_name="northern-ireland")
        elif data["country"] == "Scotland":
            return redirect("frontdoor:page", session_id=session_id, page_name="scotland")
        else:
            return super().handle_post(request, session_id, page_name, data, is_change_page)


@register_page("own-property")
class OwnPropertyView(PageView):
    def get_context(self, *args, **kwargs):
        return {"own_property_options": schemas.own_property_options}


@register_page("address")
class AddressView(PageView):
    pass


@register_page("address-select")
class AddressSelectView(PageView):
    def get_context(self, request, session_id, *args, **kwargs):
        data = interface.api.session.get_answer(session_id, "address")
        text = f"{data['address_line_1'], data['postcode']}"
        addresses = interface.api.address.find_addresses(text)
        uprn_options = tuple({"value": a["uprn"], "label": a["address"]} for a in addresses)
        return {"uprn_options": uprn_options}

    def handle_post(self, request, session_id, page_name, data, is_change_page):
        uprn = request.POST["uprn"]
        epc_rating = portal_models.EpcRating.objects.filter(uprn=uprn)
        if epc_rating.count() > 0:
            data = interface.api.address.get_address(uprn)
            _ = interface.api.session.save_answer(session_id, page_name, data)
            return redirect("frontdoor:page", session_id=session_id, page_name="epc-found")
        else:
            return redirect("frontdoor:page", session_id=session_id, page_name="council-tax-band")


@register_page("epc-found")
class EpcFoundView(PageView):
    def get_context(self, request, session_id, page_name, data):
        uprn = interface.api.session.get_answer(session_id, "address-select").get("uprn")
        epc_rating = portal_models.EpcRating.objects.filter(uprn=uprn).first()
        address = interface.api.session.get_answer(session_id, "address-select").get("address")
        context = {
            "epc_rating": epc_rating,
            "epc_found_options": schemas.epc_found_options,
            "address": address,
        }
        return context

    def handle_post(self, request, session_id, page_name, data, is_change_page):
        choice = request.POST["accept_suggested_epc"]
        if choice == "Yes":
            uprn = interface.api.session.get_answer(session_id, "address-select").get("uprn")
            epc_rating = portal_models.EpcRating.objects.filter(uprn=uprn).first()
            _ = interface.api.session.save_answer(
                session_id, page_name, {"accept_suggested_epc": True}
            )
            _ = interface.api.session.save_answer(
                session_id, "council-tax-band", {"council_tax_band": epc_rating.rating}
            )
            return redirect("frontdoor:page", session_id=session_id, page_name="benefits")
        else:
            _ = interface.api.session.save_answer(session_id, page_name, {"accept_suggested_epc": False})
            return redirect("frontdoor:page", session_id=session_id, page_name="council-tax-band")


@register_page("address-manual")
class AddressManualView(PageView):
    def get_context(self, request, session_id, *args, **kwargs):
        data = interface.api.session.get_answer(session_id, "address")
        return {"data": data}

    def handle_post(self, request, session_id, page_name, data, is_change_page):
        prev_page_name, next_page_name = get_prev_next_page_name(page_name)
        return redirect("frontdoor:page", session_id=session_id, page_name=next_page_name)


@register_page("council-tax-band")
class CouncilTaxBandView(PageView):
    def get(self, request, session_id, page_name, errors=None, is_change_page=False, override_prev_page_url=None):
        override_prev_page_url = reverse("frontdoor:page", args=[session_id, "address"])
        return super().get(request, session_id, page_name, errors, is_change_page, override_prev_page_url)

    def get_context(self, request, session_id, *args, **kwargs):
        uprn = interface.api.session.get_answer(session_id, "address-select")["uprn"]
        epc_rating = portal_models.EpcRating.objects.filter(uprn=uprn).first()
        context = {"council_tax_band_options": schemas.council_tax_band_options}
        if not epc_rating:
            return context
        else:
            context["estimated_rating"] = epc_rating.rating
            return context


@register_page("benefits")
class BenefitsView(PageView):
    def get(self, request, session_id, page_name, errors=None, is_change_page=False, override_prev_page_url=None):
        accepted_ecp_suggestion = interface.api.session.get_answer(session_id, "epc-found")["accept_suggested_epc"]
        if accepted_ecp_suggestion:
            prev_page_name = "epc-found"
        else:
            prev_page_name = "council-tax-band"
        override_prev_page_url = reverse("frontdoor:page", args=[session_id, prev_page_name])
        return super().get(request, session_id, page_name, errors, is_change_page, override_prev_page_url)

    def get_context(self, request, session_id, *args, **kwargs):
        # TODO: Figure out setting back button based on "council-tax-band:accept_suggested_epc" var in page data
        context = interface.api.session.get_session(session_id)
        return {"benefits_options": schemas.yes_no_options, "context": context}


@register_page("household-income")
class HouseholdIncomeView(PageView):
    def get_context(self, *args, **kwargs):
        return {"household_income_options": schemas.household_income_options}


@register_page("property-type")
class PropertyTypeView(PageView):
    def get_context(self, *args, **kwargs):
        return {"property_type_options": schemas.property_type_options}


@register_page("property-subtype")
class PropertySubtypeView(PageView):
    def get_context(self, request, session_id, *args, **kwargs):
        data = interface.api.session.get_answer(session_id, "property-type")
        property_type = data["property_type"]
        return {
            "property_type": property_type,
            "property_subtype_options": schemas.property_subtype_options_map[property_type],
        }


@register_page("number-of-bedrooms")
class NumberOfBedroomsView(PageView):
    def get_context(self, *args, **kwargs):
        return {"number_of_bedrooms_options": schemas.number_of_bedrooms_options}


@register_page("wall-type")
class WallTypeView(PageView):
    def get_context(self, *args, **kwargs):
        return {"wall_type_options": schemas.wall_type_options}


@register_page("wall-insulation")
class WallInsulationView(PageView):
    def get_context(self, *args, **kwargs):
        return {"wall_insulation_options": schemas.wall_insulation_options}


@register_page("loft")
class LoftView(PageView):
    def get_context(self, *args, **kwargs):
        return {"loft_options": schemas.yes_no_options}


@register_page("loft-access")
class LoftAccessView(PageView):
    def get_context(self, *args, **kwargs):
        return {"loft_access_options": schemas.loft_access_options}


@register_page("summary")
class SummaryView(PageView):
    def get_context(self, request, session_id, *args, **kwargs):
        summary_lines = (
            {
                "question": schemas.page_map[page],
                "answer": ", ".join(
                    str(value) for value in interface.api.session.get_answer(session_id, page).values()
                ),
                "change_url": reverse("frontdoor:change-page", kwargs=dict(session_id=session_id, page_name=page)),
            }
            for page in schemas.household_pages
        )
        return {"summary_lines": summary_lines}


@register_page("schemes")
class SchemesView(PageView):
    def get_context(self, request, session_id, *args, **kwargs):
        benefits_data = interface.api.session.get_answer(session_id, "benefits")
        eligible_schemes = schemas.schemes_map[benefits_data["benefits"]]
        return {"eligible_schemes": eligible_schemes}


@register_page("supplier")
class SupplierView(PageView):
    def get_context(self, *args, **kwargs):
        return {"supplier_options": schemas.supplier_options}


@register_page("contact-details")
class ContactDetailsView(PageView):
    pass


@register_page("confirm-and-submit")
class ConfirmSubmitView(PageView):
    def get_context(self, request, session_id, *args, **kwargs):
        summary_lines = tuple(
            {
                "question": schemas.question_map[key],
                "answer": value,
                "change_url": reverse("frontdoor:change-page", kwargs=dict(session_id=session_id, page_name=page_name)),
            }
            for page_name in schemas.details_pages
            for key, value in interface.api.session.get_answer(session_id, page_name).items()
        )
        return {"summary_lines": summary_lines}

    def handle_post(self, request, session_id, page_name, data, is_change_page):
        interface.api.session.create_referral(session_id)
        return super().handle_post(request, session_id, page_name, data, is_change_page)


@register_page("success")
class SuccessView(PageView):
    def get_context(self, session_id, *args, **kwargs):
        supplier_data = interface.api.session.get_answer(session_id, "supplier")
        return {"supplier": supplier_data["supplier"]}


def page_view(request, session_id, page_name):
    if page_name in page_map:
        return page_map[page_name](request, session_id, page_name)

    context = {"session_id": session_id, "page_name": page_name}
    return render(request, template_name=f"frontdoor/{page_name}.html", context=context)


def change_page_view(request, session_id, page_name):
    assert page_name in page_map
    return page_map[page_name](request, session_id, page_name, is_change_page=True)
