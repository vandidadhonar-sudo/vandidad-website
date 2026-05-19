import { useState } from 'react'
import { motion } from 'framer-motion'
import { useLanguage } from '../context/LanguageContext'

const DATA = {
  fa: {
    label:'[ تماس ]', heading:'کسب‌وکار شما، شناسنامه شماست',
    desc:'جای بیزنس شما در ابزارهای عمومی نیست. برای سنجش زیرساخت‌های صنف خود و درخواست معماری یک مغز متفکر اختصاصی، بذر گفت‌وگو را بکارید.',
    fields:['نام و نام خانوادگی / شرکت','صنف و حوزه فعالیت تجاری','چالش کلان یا هدف مدنظر برای خودکارسازی'],
    btn:'درخواست مشاوره استراتژیک VIP',
    mailLabel:'درگاه ارتباط رسمی سازمانی',
    footer:'© 2026 Vandidad Group. All Rights Reserved.',
  },
  en: {
    label:'[ CONTACT ]', heading:'Your Enterprise Is Your Identity',
    desc:'Your legacy does not belong in generic tools. Sow the seeds of transformation to audit your infrastructure for a custom cognitive brain.',
    fields:['Full Name / Corporate Entity','Industry / Sector','Core Bottleneck / Automation Objective'],
    btn:'Request Strategic VIP Consultation',
    mailLabel:'Secure Enterprise Gateway',
    footer:'© 2026 Vandidad Group. All Rights Reserved.',
  },
  tr: {
    label:'[ İLETİŞİM ]', heading:'Şirketiniz Sizin Kimliğinizdir',
    desc:'Ticari mirasınız sıradan araçlara ait değildir. Stratejik görüşme talebinde bulunun.',
    fields:['Ad Soyad / Şirket','Sektör','En Büyük Engel / Otomasyon Hedefi'],
    btn:'VIP Stratejik Danışmanlık Talebi',
    mailLabel:'Resmi Kurumsal İletişim',
    footer:'© 2026 Vandidad Group. All Rights Reserved.',
  },
  ar: {
    label:'[ التواصل ]', heading:'عملك التجاري هو هويتك',
    desc:'مكانة عملك ليست في الأدوات العامة. ضع بذور التحول لترقية بنيتك التحتية.',
    fields:['الاسم الكامل / اسم الشركة','القطاع والمجال','العقبة الرئيسية / هدف الأتمتة'],
    btn:'طلب استشارة استراتيجية VIP',
    mailLabel:'بوابة التواصل الرسمي',
    footer:'© 2026 Vandidad Group. All Rights Reserved.',
  },
  de: {
    label:'[ KONTAKT ]', heading:'Ihr Unternehmen ist Ihre Identität',
    desc:'Ihr Erbe gehört nicht in generische Tools. Legen Sie den Grundstein für Transformation.',
    fields:['Name / Unternehmen','Branche','Hauptengpass / Automatisierungsziel'],
    btn:'VIP-Strategieberatung anfragen',
    mailLabel:'Sicheres Unternehmensportal',
    footer:'© 2026 Vandidad Group. All Rights Reserved.',
  },
}

export default function ContactSection() {
  const { lang } = useLanguage()
  const d = DATA[lang] || DATA.fa
  const isRtl = lang === 'fa' || lang === 'ar'
  const [focus, setFocus] = useState(null)
  const [sent, setSent] = useState(false)

  const inputStyle = (i) => ({
    width:'100%', background:'transparent',
    border:'none', borderBottom: focus===i
      ? '1px solid #00F2FE' : '1px solid rgba(255,255,255,0.12)',
    color:'#fff', padding:'12px 0',
    fontFamily:'Vazirmatn,Inter,sans-serif', fontSize:'14px',
    outline:'none', transition:'border-color 0.3s',
    boxShadow: focus===i ? '0 1px 0 0 rgba(0,242,254,0.4)' : 'none',
    textAlign: isRtl ? 'right' : 'left',
  })

  return (
    <section style={{
      background:'linear-gradient(180deg,#050A1E 0%,#020510 100%)',
      borderTop:'1px solid rgba(255,255,255,0.04)',
      padding:'clamp(60px,10vh,120px) clamp(20px,6vw,80px) 0',
      direction: isRtl ? 'rtl' : 'ltr',
    }}>
      <div style={{ maxWidth:'900px', margin:'0 auto' }}>

        <motion.div initial={{ opacity:0,y:30 }} whileInView={{ opacity:1,y:0 }}
          viewport={{ once:true }} transition={{ duration:0.7 }}
          style={{ textAlign:'center', marginBottom:'clamp(36px,6vh,60px)' }}>
          <div style={{ fontFamily:'"Courier New",monospace', fontSize:'11px',
            letterSpacing:'0.25em', color:'rgba(0,242,254,0.5)',
            textTransform:'uppercase', marginBottom:'16px' }}>{d.label}</div>
          <h2 style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
            fontSize:'clamp(1.6rem,3.5vw,3rem)', fontWeight:900,
            color:'#fff', marginBottom:'16px' }}>{d.heading}</h2>
          <p style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
            fontSize:'clamp(0.85rem,1.1vw,1rem)', color:'rgba(180,200,230,0.55)',
            maxWidth:'600px', margin:'0 auto', lineHeight:2 }}>{d.desc}</p>
        </motion.div>

        <motion.div initial={{ opacity:0,y:30 }} whileInView={{ opacity:1,y:0 }}
          viewport={{ once:true }} transition={{ duration:0.7, delay:0.2 }}
          style={{ maxWidth:'560px', margin:'0 auto clamp(40px,7vh,70px)' }}>
          {!sent ? (
            <form onSubmit={(e)=>{ e.preventDefault(); setSent(true) }}
              style={{ display:'flex', flexDirection:'column', gap:'28px' }}>
              {d.fields.map((label, i) => (
                <div key={i}>
                  <label style={{ fontFamily:'"Courier New",monospace', fontSize:'10px',
                    letterSpacing:'0.2em', color:'rgba(0,242,254,0.6)',
                    textTransform:'uppercase', display:'block', marginBottom:'8px' }}>
                    {label}
                  </label>
                  {i === 2
                    ? <textarea rows={2} required
                        onFocus={()=>setFocus(i)} onBlur={()=>setFocus(null)}
                        style={{ ...inputStyle(i), resize:'none' }}/>
                    : <input type="text" required
                        onFocus={()=>setFocus(i)} onBlur={()=>setFocus(null)}
                        style={inputStyle(i)}/>
                  }
                </div>
              ))}
              <button type="submit" style={{
                background:'linear-gradient(90deg,rgba(0,242,254,0.1),rgba(168,85,247,0.1))',
                border:'1px solid rgba(0,242,254,0.3)', color:'#00F2FE',
                fontFamily:'"Courier New",monospace', fontSize:'11px',
                letterSpacing:'0.2em', textTransform:'uppercase',
                padding:'16px 32px', cursor:'pointer',
                transition:'all 0.3s', borderRadius:'4px',
              }}
              onMouseEnter={e=>{ e.target.style.background='rgba(0,242,254,0.12)'; e.target.style.boxShadow='0 0 30px rgba(0,242,254,0.2)' }}
              onMouseLeave={e=>{ e.target.style.background='linear-gradient(90deg,rgba(0,242,254,0.1),rgba(168,85,247,0.1))'; e.target.style.boxShadow='none' }}>
                {d.btn}
              </button>
            </form>
          ) : (
            <motion.div initial={{ opacity:0,scale:0.9 }} animate={{ opacity:1,scale:1 }}
              style={{ textAlign:'center', padding:'40px',
                border:'1px solid rgba(0,242,254,0.2)', borderRadius:'8px',
                background:'rgba(0,242,254,0.04)' }}>
              <div style={{ fontSize:'32px', marginBottom:'16px' }}>✓</div>
              <p style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
                color:'#00F2FE', fontSize:'16px' }}>
                {lang==='fa'?'درخواست ثبت شد. به زودی در تماس خواهیم بود.':
                 lang==='ar'?'تم تسجيل طلبك. سنتواصل معك قريباً.':
                 lang==='tr'?'Talebiniz alındı. Kısa sürede iletişime geçeceğiz.':
                 'Request received. We will be in touch shortly.'}
              </p>
            </motion.div>
          )}
        </motion.div>

        {/* Email */}
        <motion.div initial={{ opacity:0 }} whileInView={{ opacity:1 }}
          viewport={{ once:true }} transition={{ duration:0.8, delay:0.3 }}
          style={{ textAlign:'center', paddingBottom:'clamp(40px,7vh,70px)' }}>
          <div style={{ fontFamily:'"Courier New",monospace', fontSize:'10px',
            letterSpacing:'0.25em', color:'rgba(255,255,255,0.25)',
            textTransform:'uppercase', marginBottom:'10px' }}>{d.mailLabel}</div>
          <a href="mailto:ai@vandidad.xyz" style={{
            fontFamily:'"Courier New",Inter,sans-serif',
            fontSize:'clamp(1rem,2vw,1.4rem)', fontWeight:500,
            color:'#fff', textDecoration:'none', letterSpacing:'0.05em',
            transition:'color 0.3s',
          }}
          onMouseEnter={e=>e.target.style.color='#00F2FE'}
          onMouseLeave={e=>e.target.style.color='#fff'}>
            ai@vandidad.xyz
          </a>
        </motion.div>

        {/* Footer */}
        <div style={{
          borderTop:'1px solid rgba(255,255,255,0.05)',
          padding:'24px 0', textAlign:'center',
          fontFamily:'"Courier New",monospace', fontSize:'10px',
          letterSpacing:'0.2em', color:'rgba(255,255,255,0.2)',
        }}>{d.footer}</div>
      </div>
    </section>
  )
}
