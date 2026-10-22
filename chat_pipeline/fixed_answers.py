"""Configured clinic information, never a claim that live slots were checked.

Only complete, single-topic utterances match. Named doctors, dates, other clinics,
and compound requests continue to the existing live clinic/RAG handlers.
"""
import re

from django.conf import settings

from .patterns import normalize

ANSWERS = {
    'hours': {
        'EN': 'OneCare clinic is open from {opening} to {closing}.',
        'TA': 'OneCare கிளினிக் மாலை 5:00 மணி முதல் இரவு 11:00 மணி வரை திறந்திருக்கும்.',
    },
    'doctors': {
        'EN': 'Yes, the doctor is available today from {opening} to {closing}.',
        'TA': 'ஆம், இன்று மருத்துவர் மாலை 5:00 மணி முதல் இரவு 11:00 மணி வரை இருப்பார்',
    },
    'booking': {
        'EN': 'You can book an appointment through the OneCare patient portal. Click the button below to go to the appointment booking page.',
        'TA': 'OneCare நோயாளர் இணையதளத்தின் மூலம் நீங்கள் மருத்துவர் நேரத்தை முன்பதிவு செய்யலாம். முன்பதிவு பக்கத்திற்குச் செல்ல கீழே உள்ள பொத்தானை அழுத்தவும்.',
    },
    'services': {
        'EN': '\n'.join([  # noqa: FLY002 - keep each approved service separately reviewable.
            '1. Doctor Appointment Booking – Book appointments with available doctors.',
            '2. Doctor Availability – Check doctors and available appointment slots.',
            '3. Clinic Opening Hours – Find clinic opening and closing times.',
            '4. Patient Registration – Register and manage your patient profile.',
            '5. Appointment Management – View and manage appointments.',
            '6. General Medical Consultation – Access information about medical consultation services.',
            '7. Health Education – Get general healthcare information and awareness resources.',
            '8. AI Chatbot Assistance – Ask questions about clinic hours, appointments, doctors, and services.',
        ]),
        'TA': '\n'.join([  # noqa: FLY002 - keep translations aligned with the English list.
            '1. மருத்துவர் முன்பதிவு – மருத்துவர்களிடம் சந்திப்புகளை முன்பதிவு செய்யுங்கள்.',
            '2. மருத்துவர் வருகை – மருத்துவர்கள் மற்றும் முன்பதிவு நேரங்களைச் சரிபாருங்கள்.',
            '3. கிளினிக் நேரம் – திறக்கும் மற்றும் மூடும் நேரங்களை அறியுங்கள்.',
            '4. நோயாளர் பதிவு – உங்கள் நோயாளர் விவரங்களைப் பதிவு செய்து நிர்வகியுங்கள்.',
            '5. முன்பதிவு நிர்வாகம் – உங்கள் முன்பதிவுகளைப் பார்த்து நிர்வகியுங்கள்.',
            '6. பொது மருத்துவ ஆலோசனை – மருத்துவ ஆலோசனை சேவைகள் பற்றிய தகவல்களைப் பெறுங்கள்.',
            '7. சுகாதாரக் கல்வி – பொதுச் சுகாதாரத் தகவல்களைப் பெறுங்கள்.',
            '8. AI உதவியாளர் – கிளினிக் நேரம், முன்பதிவுகள், மருத்துவர்கள் மற்றும் சேவைகள் பற்றிக் கேளுங்கள்.',
        ]),
    },
}

# Anchored patterns deliberately favour precision over guessing the clinic identity.
PATTERNS = {
    'hours': [
        r'(?:what (?:are|is) (?:the |your |onecare )?)?(?:onecare )?(?:clinic )?(?:opening |closing )?(?:hours|time)',
        r'when does (?:onecare|the clinic|onecare clinic) (?:open|close)',
        r'what time does (?:onecare|the clinic|onecare clinic) (?:open|close)',
        r'(?:onecare )?கிளினிக் (?:நேரம்(?: என்ன)?|எப்போது திறக்கும்|எப்போது மூடும்|திறக்கும் நேரம் என்ன|மூடும் நேரம் என்ன)',
    ],
    'doctors': [
        r'(?:is (?:a |the )?)?doctor(?:s)? (?:available today|availability today)',
        r'what time is (?:the |a )?doctor available',
        r'can i see (?:a |the )?doctor today',
        r'இன்று மருத்துவர்(?: இருக்கிறாரா| கிடைப்பாரா)?',
        r'மருத்துவர் இன்று (?:இருக்கிறாரா|கிடைப்பாரா)',
        r'மருத்துவர் (?:எப்போது|எந்த நேரத்தில்) (?:இருப்பார்|கிடைப்பார்)',
    ],
    'booking': [
        r'(?:how (?:can|do) i |how to |where can i )(?:book|make) (?:a doctor |an? )?appointment',
        r'முன்பதிவு செய்வது எப்படி',
        r'அப்பாயிண்ட்மென்ட் எப்படி பதிவு செய்வது',
        r'(?:மருத்துவர் நேரத்தை |மருத்துவரிடம் )?எப்படி முன்பதிவு செய்வது',
    ],
    'services': [
        r'services offered',
        r'what (?:services (?:does (?:onecare|the clinic) (?:provide|offer)|are available)|are (?:your|the clinic) services)',
        r'கிளினிக்(?:கில்)? (?:சேவைகள்|என்னென்ன சேவைகள் உள்ளன|என்ன சேவைகள்)',
        r'(?:onecare )?என்ன சேவைகள் (?:உள்ளன|வழங்கப்படுகின்றன)',
    ],
}


def detect_intent(query):
    text = normalize(query).rstrip('?.! ')
    return next((intent for intent, patterns in PATTERNS.items()
                 if any(re.fullmatch(pattern, text) for pattern in patterns)), None)


def mentions_other_clinic(query):
    return bool(re.search(r'\b(?!(?:onecare|the|your|our|this|a)\b)[\w-]+\s+(?:clinic|hospital)\b', normalize(query)))


def answer(query, language):
    if not getattr(settings, 'CHAT_FIXED_CLINIC_ENABLED', True):
        return None
    intent = detect_intent(query)
    if intent is None:
        return None
    overrides = getattr(settings, 'CHAT_FIXED_CLINIC_ANSWERS', {})
    template = overrides.get(intent, {}).get(language, ANSWERS[intent][language])
    result = {'message': template.format(opening='5:00 PM', closing='11:00 PM'),
              'clinicInfoSource': 'CONFIGURED'}
    if intent == 'booking':
        result['action'] = {'type': 'BOOK_APPOINTMENT'}
    return result
