import { useLanguage } from './context/LanguageContext'
import HeroSection from './components/HeroSection'
import ProblemSection from './components/ProblemSection'
import AIOSSection from './components/AIOSSection'
import PortfolioSection from './components/PortfolioSection'
import LegacySection from './components/LegacySection'
import ContactSection from './components/ContactSection'

export default function App() {
  const { lang, setLang, t } = useLanguage()

  return (
    <div style={{ background:'#050A1E', color:'#F1F5F9', overflowX:'hidden' }}>

      <header style={{
        position:'sticky', top:0, zIndex:50,
        background:'rgba(5,10,30,0.88)',
        backdropFilter:'blur(24px)',
        borderBottom:'1px solid rgba(0,242,254,0.08)',
        padding:'14px 24px',
      }}>
        <div style={{ maxWidth:'1280px', margin:'0 auto', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
          <div dir="ltr" style={{ fontSize:'13px', fontWeight:900, letterSpacing:'0.15em', textTransform:'uppercase', background:'linear-gradient(90deg,#00F2FE,#818CF8,#A855F7)', WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent' }}>
            {t('brand')}
          </div>
          <div dir="ltr" style={{ display:'flex', gap:'20px' }}>
            {['fa','en','tr','ar'].map((l) => (
              <button key={l} onClick={() => setLang(l)} style={{ fontSize:'11px', letterSpacing:'0.12em', textTransform:'uppercase', background:'none', border:'none', cursor:'pointer', color: lang===l ? '#00F2FE' : 'rgba(255,255,255,0.35)', fontWeight: lang===l ? 700 : 400, textShadow: lang===l ? '0 0 12px rgba(0,242,254,0.8)' : 'none', transition:'all 0.3s' }}>
                {l==='fa'?'فارسی':l==='ar'?'العربية':l.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </header>

      <HeroSection />
      <ProblemSection />
      <AIOSSection />
      <PortfolioSection />
      <LegacySection />
      <ContactSection />

    </div>
  )
}
