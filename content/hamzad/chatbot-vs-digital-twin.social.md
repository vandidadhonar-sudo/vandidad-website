## instagram
این پیامِ واقعیِ یه مشتریه:

«دو هفته پیش سفارش دادم، هنوز نرسیده، اگه قراره باز دیر بشه بی‌خیالش می‌شم.»

سه تا کنشِ جدا توش هست: پیگیری، نارضایتی، و اعلامِ شرطیِ انصراف. چت‌بات‌های مبتنی بر تشخیص نیت، دسته‌بندیِ تک‌برچسبی می‌کنن — یعنی فقط یکی‌شو برمی‌دارن و دو تای دیگه حذف می‌شه. توی لاگ هم دیده نمی‌شه، چون سیستم فکر می‌کنه موفق بوده.

و اون دوتای حذف‌شده، مهم‌ترین بخشِ پیام بودن. سومی سیگنالِ ریزشه.

تحلیل کامل سه مسئلهٔ مهندسی پشت این ماجرا رو نوشتم:
vandidad.xyz/hamzad/chatbot-vs-digital-twin?from=ig

#هوش_مصنوعی #چت_بات #ایجنت_هوشمند #معماری_نرم_افزار #کسب_وکار

## telegram
**چرا چت‌بات‌ها روی پیام واقعی مشتری شکست می‌خورند**

تشخیصِ رایج این است که «مدل فارسی را خوب نمی‌فهمد». این تشخیص غلط است — و چون غلط است، انتخاب بعدی هم غلط می‌شود.

سه مسئلهٔ مهندسیِ جدا در کار است:

۱. دسته‌بندیِ تک‌برچسبی، جمله‌ای که چند نیت دارد را به یک نیت فرو می‌کاهد.
۲. نبودِ مدلِ وضعیت — هویت، نشست و پرونده معمولاً یکی گرفته می‌شوند، در حالی که یک نفر می‌تواند هم‌زمان دو پروندهٔ باز داشته باشد.
۳. تولید بدونِ راهِ امتناع — مدلی که همیشه باید چیزی بگوید، وقتی نداند، می‌سازد.

هر سه در معماری حل می‌شوند، نه با عوض کردن مدل. تحلیل کامل:

vandidad.xyz/hamzad/chatbot-vs-digital-twin?from=tg

## linkedin
The common diagnosis for a failed chatbot is that the model does not handle Persian well. That diagnosis is wrong, and it leads to the wrong next decision.

Three separate engineering problems are at work: single-label intent classification collapsing multi-intent utterances, the absence of a state model that separates identity from session from case, and generation without a refusal path.

None of them is a language problem. All three are resolved in architecture.

Full technical analysis by Hadi Bakhtzadeh, AI systems architect at Vandidad Group:
vandidad.xyz/hamzad/chatbot-vs-digital-twin?from=li
