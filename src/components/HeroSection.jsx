import { Suspense } from 'react'
import Spline from '@splinetool/react-spline'
import { useLanguage } from '../context/LanguageContext'

export default function HeroSection() {
  const { lang, t } = useLanguage()
  const isRtl = lang === 'fa' || lang === 'ar'

  const highlight = {
    background: 'linear-gradient(90deg,#00F2FE,#A855F7)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  }

  const headlines = {
    fa: <>من ابزار نمی‌سازم؛ من <span style={highlight}>سیستم تصمیم‌گیر</span> طراحی می‌کنم.</>,
    en: <>I architect <span style={highlight}>decision systems</span>.</>,
    tr: <><span style={highlight}>Karar sistemleri</span> tasarlıyorum.</>,
    ar: <>أصمم <span style={highlight}>أنظمة القرار</span>.</>,
    de: <>Ich entwerfe <span style={highlight}>Entscheidungssysteme</span>.</>,
  }

  return (
    <section style={{ position:'relative', height:'100svh', minHeight:'600px', overflow:'hidden', background:'#000' }}>

      {/* Spline — fully interactive, pointer events ON */}
      <Suspense fallback={
        <div style={{ position:'absolute', inset:0, background:'#000',
          display:'flex', alignItems:'center', justifyContent:'center' }}>
          <span style={{ fontFamily:'"Courier New",monospace', fontSize:'11px',
            letterSpacing:'0.3em', color:'rgba(0,242,254,0.4)' }}>LOADING...</span>
        </div>
      }>
        <Spline
          scene="https://prod.spline.design/C3y8kgxE8MwkEDaC/scene.splinecode"
          style={{ position:'absolute', inset:0, width:'100%', height:'100%', zIndex:1 }}
        />
      </Suspense>

      {/* Side gradient — only on text side, NOT covering the character */}
      <div style={{
        position:'absolute', inset:0, zIndex:2, pointerEvents:'none',
        background: isRtl
          ? 'linear-gradient(to left, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.6) 35%, transparent 60%)'
          : 'linear-gradient(to right, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.6) 35%, transparent 60%)',
      }}/>

      {/* ── Desktop: side panel, centered vertically ── */}
      <div style={{
        position:'absolute', top:0, bottom:0,
        left: isRtl ? 'auto' : 0,
        right: isRtl ? 0 : 'auto',
        width:'44%',
        zIndex:3,
        display:'flex', flexDirection:'column', justifyContent:'center',
        padding: isRtl ? '0 5vw 0 1vw' : '0 1vw 0 5vw',
        direction: isRtl ? 'rtl' : 'ltr',
        pointerEvents:'none',
      }}
      className="hero-text-desktop">

        {/* Badge */}
        <div style={{
          display:'inline-flex', alignItems:'center', gap:'8px',
          width:'fit-content', marginBottom:'20px',
          background:'rgba(0,242,254,0.07)',
          border:'1px solid rgba(0,242,254,0.25)',
          borderRadius:'999px', padding:'5px 14px',
        }}>
          <span style={{ width:'6px', height:'6px', borderRadius:'50%', flexShrink:0,
            background:'#00F2FE', boxShadow:'0 0 8px #00F2FE', display:'inline-block' }}/>
          <span style={{ fontFamily:'"Courier New",monospace',
            fontSize:'clamp(8px,0.9vw,10px)', letterSpacing:'0.18em',
            color:'#00F2FE', textTransform:'uppercase', whiteSpace:'nowrap',
          }}>{t('badge')}</span>
        </div>

        <p style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
          fontSize:'clamp(0.75rem,1.1vw,0.95rem)',
          color:'rgba(200,215,255,0.6)', fontWeight:300,
          lineHeight:1.9, marginBottom:'12px',
        }}>{t('heroStatement')}</p>

        <h1 style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
          fontSize:'clamp(1.3rem,2.8vw,2.8rem)',
          fontWeight:900, color:'#fff',
          lineHeight:1.4, marginBottom:'14px',
        }}>{headlines[lang] || headlines.fa}</h1>

        <p style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
          fontSize:'clamp(0.75rem,0.95vw,0.9rem)',
          color:'#00F2FE', fontWeight:600,
          textShadow:'0 0 16px rgba(0,242,254,0.4)', lineHeight:1.7,
        }}>{t('heroTitle')}</p>
      </div>

      {/* ── Mobile: bottom text, pointer-events none so Spline stays touchable ── */}
      <style>{`
        @media (max-width: 768px) {
          .hero-text-desktop {
            width: 100% !important;
            left: 0 !important;
            right: 0 !important;
            top: auto !important;
            bottom: 0 !important;
            justify-content: flex-end !important;
            padding: 0 5vw 5vh !important;
            background: linear-gradient(to top, rgba(0,0,0,0.95) 0%, transparent 100%);
          }
        }
      `}</style>

    </section>
  )
}
