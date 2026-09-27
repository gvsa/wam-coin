#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
Does the wallet still call the coin Bitcoin in somebody else's alphabet?

On 2026-09-27 the founder opened the Windows wallet in Arabic, went to the
send tab, and read:

    ادخل عنوان محفطة البتكوين (مثال wam1p35yvjel7srp783ztf8v6jd)

The address was ours and the sentence was not. Every check the project had
was written in Latin letters and so could not see it; 95 of the 123 shipped
catalogues were in the same state.

Two halves are tested here, and the second is the one that matters:

  1. the table of spellings rewrites what it knows;
  2. the rule that reads a word by SOUND rewrites what nobody listed --
     because the table has been incomplete three times now, and a fourth
     list would be a fourth guess.

The controls are not decoration. A rule that rewrites the coin's name in
every script on earth is one bad pattern away from rewriting the word
"network" in Korean, and nobody here would be able to read the damage.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rebrand_qt as R                                    # noqa: E402

# A Windows console is cp1252 and raises on the first Arabic character, which
# would turn a failing check into a traceback about printing.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')

failures = []


def check(what, got, want):
    if got == want:
        print(f'  ok    {what}')
    else:
        print(f'  FAIL  {what}\n          got:  {got}\n          want: {want}')
        failures.append(what)


# The sentence he photographed, and the rest of the send tab in the languages
# this project already has a person using.
NAMED = [
    ('ar', 'ادخل عنوان محفطة البتكوين (مثال %1)', 'ادخل عنوان محفطة WAM (مثال %1)'),
    ('fa', 'یک آدرس بیت‌کوین وارد کنید', 'یک آدرس WAM وارد کنید'),
    ('he', 'נא לספק כתובת ביטקוין', 'נא לספק כתובת WAM'),
    ('ru', 'Введите биткоин-адрес', 'Введите WAM-адрес'),
    ('uk', 'Введіть біткойн-адресу', 'Введіть WAM-адресу'),
    ('ko', '비트코인 주소를 입력하세요', 'WAM 주소를 입력하세요'),
    ('ja', 'ビットコインアドレス', 'WAMアドレス'),
    ('zh', '请输入一个比特币地址', '请输入一个WAM地址'),
    ('hi', 'एक बिटकॉइन पता दर्ज करें', 'एक WAM पता दर्ज करें'),
    # Georgian keeps its genitive ending on the borrowed word, and should:
    # WAMის is "of WAM", which is what the sentence says.
    ('ka', 'ბიტკოინის მისამართი', 'WAMის მისამართი'),
    ('am', 'ቢትኮይን አድራሻ', 'WAM አድራሻ'),
    ('ur', 'بٹ کوائن کا پتہ', 'WAM کا پتہ'),
]

# Sentences that name no coin. Every one of these must come back untouched:
# they are what a too-eager rule would quietly destroy.
UNTOUCHED = [
    ('ru', 'Кошелёк зашифрован'),
    ('ko', '네트워크 연결이 끊어졌습니다'),
    ('zh', '确认发送货币'),
    ('hi', 'नेटवर्क से कनेक्शन टूट गया'),
    ('he', 'הארנק הוצפן בהצלחה'),
    ('ar', 'إرسال العملات إلى العنوان أدناه'),
    ('en', 'Send coins to the address below'),
    ('ja', 'ウォレットが暗号化されました'),
]

print('the name, in the script each language writes it in')
for lang, before, after in NAMED:
    check(f'{lang}: the coin is renamed', R.rewrite(before), after)

print('\nand the sentences that name no coin, which must not move')
for lang, text in UNTOUCHED:
    check(f'{lang}: left alone', R.rewrite(text), text)

# THE HALF THAT DOES NOT DEPEND ON THE LIST BEING RIGHT.
#
# Same sentences, with the table taken away. Whatever still gets renamed was
# renamed by reading the word aloud, which is the part that will still work
# on a language upstream adds next year.
print('\nwith the table of spellings removed, so only the sound rule is left')
BY_SOUND = ['ar', 'fa', 'he', 'ru', 'uk', 'ko', 'ja', 'hi', 'ka', 'am', 'ur']

# Arabic glues its article to the word, and stripping it is a nicety the
# table does and the sound rule does not: on its own the rule leaves الWAM,
# an article stuck to a Latin word. Ugly, and still the right outcome -- it
# no longer names another coin, which is all the safety net is for.
#
# Georgian names its vowels with consonants in them -- GEORGIAN LETTER IN is
# the letter i -- so the skeleton sees an n where the ear hears none, and the
# rule swallows one letter of the case ending with the word. WAMს instead of
# WAMის: a grammatical ending short, not a coin's name wrong. The table has
# the exact Georgian spelling and produces the right form; this is only what
# the net underneath would catch if the table did not.
ALONE = {'ar': 'ادخل عنوان محفطة الWAM (مثال %1)',
         'ka': 'WAMს მისამართი'}

for lang, before, after in NAMED:
    if lang not in BY_SOUND:
        continue                      # Han carries no sound in its codepoints
    check(f'{lang}: renamed by sound alone',
          R.rewrite_by_sound(before), ALONE.get(lang, after))

for lang, text in UNTOUCHED:
    check(f'{lang}: sound rule leaves it alone', R.rewrite_by_sound(text), text)

print()
if failures:
    print(f'{len(failures)} check(s) failed')
    sys.exit(1)
print(f'{len(NAMED) + len(UNTOUCHED) + len(BY_SOUND) + len(UNTOUCHED)} checks passed')
