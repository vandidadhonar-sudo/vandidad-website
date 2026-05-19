import React, { createContext, useContext, useState, useEffect } from 'react';
import fa from '../locales/fa.json';
import tr from '../locales/tr.json';
import en from '../locales/en.json';
import de from '../locales/de.json';
import ar from '../locales/ar.json';

const translations = { fa, tr, en, de, ar };
const LanguageContext = createContext();

export const LanguageProvider = ({ children }) => {
  const [lang, setLang] = useState('fa');
  
  useEffect(() => {
    const direction = lang === 'fa' || lang === 'ar' ? 'rtl' : 'ltr';
    document.documentElement.dir = direction;
    document.documentElement.lang = lang;
  }, [lang]);

  const t = (key) => {
    const keys = key.split('.');
    let result = translations[lang];
    for (const k of keys) { 
      if (result) result = result[k]; 
      else return key; 
    }
    return result || key;
  };
  
  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => useContext(LanguageContext);
