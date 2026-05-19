import React from 'react';
import { useLanguage } from '../context/LanguageContext';

const languages = [
  { code: 'fa', label: 'فارسی' },
  { code: 'tr', label: 'Türkçe' },
  { code: 'en', label: 'English' },
  { code: 'de', label: 'Deutsch' },
  { code: 'ar', label: 'العربية' }
];

export default function LanguageSwitcher() {
  const { lang, setLang } = useLanguage();

  return (
    <div className="flex gap-2 p-2 bg-neutral-900/80 backdrop-blur-md rounded-xl border border-neutral-800 w-fit mx-auto my-4">
      {languages.map((item) => (
        <button
          key={item.code}
          onClick={() => setLang(item.code)}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-300 ${
            lang === item.code
              ? 'bg-neutral-100 text-neutral-900 shadow-lg'
              : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800'
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
