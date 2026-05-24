import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { useLanguage } from '../context/LanguageContext'

const RECORDS = [
  { yr:'1383', type:'CONCERT.NATIONAL', color:'rgba(0,210,180,0.6)', fa:'کنسرت «هفتاد دف ایران»', hash:'C4F1' },
  { yr:'1384', type:'CONCERT.RECORD',   color:'rgba(0,210,180,0.6)', fa:'بزرگ‌ترین کنسرت سنتی — ۱۷۰ نوازنده', hash:'B8E2' },
  { yr:'1384', type:'EXHIBITION.FIRST', color:'rgba(120,160,255,0.6)', fa:'اولین نمایشگاه آموزشگاه‌های خاورمیانه', hash:'D3A7' },
  { yr:'1385', type:'CONCERT.MASTER',   color:'rgba(0,210,180,0.6)', fa:'کنسرت استاد جلال ذوالفنون', hash:'F901' },
  { yr:'1386', type:'CONCERT.INTL',     color:'rgba(0,210,180,0.6)', fa:'استاد علی‌اکبر مرادی + اوزدمیر', hash:'7CE4' },
  { yr:'1388', type:'CEREMONY.STATE',   color:'rgba(197,160,89,0.6)', fa:'گروه کامکارها + تمبر یادبود ملی', hash:'2AF8' },
  { yr:'1388', type:'CEREMONY.STATE',   color:'rgba(197,160,89,0.6)', fa:'بزرگداشت استاد مسعود کیمیایی', hash:'E5B3' },
  { yr:'1390', type:'CONCERT.MASTER',   color:'rgba(0,210,180,0.6)', fa:'کنسرت استاد مجید درخشانی', hash:'9D6C' },
  { yr:'1391', type:'INSTITUTE.FOUNDED',color:'rgba(220,100,100,0.6)', fa:'مدرسه سینمایی استاد کیمیایی — شیراز', hash:'A1F5' },
]

const SYSTEMS = [
  { id:'VANTA_SALES_OS', ver:'v2.4.1', pct:92, live:true },
  { id:'VANTA_LEGAL_OS', ver:'v1.2.0', pct:78, live:true },
  { id:'PANAH_AI',       ver:'α.0.7',  pct:44, live:false },
  { id:'PROFESSOR_P',    ver:'α.0.5',  pct:32, live:false },
]

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;700&display=swap');
  .arc-legacy {
    background:#04060F;
    position:relative;
    background-image:repeating-linear-gradient(0deg,rgba(0,0,0,0.055) 0px,rgba(0,0,0,0.055) 1px,transparent 1px,transparent 4px);
  }
  .arc-legacy::after {
    content:'01 AF 3C B2 E7 19 F4 8D 00 FF A2 77 39 C1 5E 0B 82 D6 4A 93 CF 28 71 EB 16 5F B8 2D 6A E3';
    position:absolute;top:0;left:0;right:0;
    font-family:'JetBrains Mono',monospace;font-size:9px;
    letter-spacing:0.18em;color:rgba(197,160,89,0.03);
    word-break:break-all;line-height:1.8;padding:8px;
    pointer-events:none;z-index:0;
  }
  .arc-rec { transition:background 0.2s; border-radius:4px; }
  .arc-rec:hover { background:rgba(197,160,89,0.03); }
  @keyframes arc-blink { 0%,100%{opacity:1} 50%{opacity:0} }
  @keyframes arc-pulse { 0%,100%{opacity:0.35} 50%{opacity:0.65} }
  .arc-blink { animation:arc-blink 1.1s step-end infinite; }
  .arc-pulse { animation:arc-pulse 3s ease-in-out infinite; }
`

export default function LegacySection() {
  const { lang } = useLanguage()
  const isRtl = lang === 'fa' || lang === 'ar'

  useEffect(() => {
    const s = document.createElement('style')
    s.textContent = CSS
    document.head.appendChild(s)
    return () => document.head.removeChild(s)
  }, [])

  const now = new Date()
  const time = now.toISOString().slice(0,19).replace('T',' ')

  return (
    <motion.section
      className="arc-legacy"
      style={{ borderTop:'1px solid rgba(197,160,89,0.08)', fontFamily:"'Vazirmatn',sans-serif", direction: isRtl ? 'rtl' : 'ltr', color:'#C8D8E8' }}
      initial={{ opacity:0, y:40 }}
      whileInView={{ opacity:1, y:0 }}
      viewport={{ once:true }}
      transition={{ duration:0.8 }}
    >
      <div style={{ position:'relative', zIndex:1 }}>

        {/* terminal bar */}
        <div style={{ background:'rgba(197,160,89,0.06)', borderBottom:'1px solid rgba(197,160,89,0.12)', padding:'10px 20px', display:'flex', alignItems:'center', gap:'12px', direction:'ltr' }}>
          <div style={{ width:11, height:11, borderRadius:'50%', background:'#FF5F57' }}/>
          <div style={{ width:11, height:11, borderRadius:'50%', background:'#FEBC2E' }}/>
          <div style={{ width:11, height:11, borderRadius:'50%', background:'#28C840' }}/>
          <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10.5, color:'rgba(197,160,89,0.55)', flex:1, letterSpacing:'0.08em' }}>
            VANDIDAD::ARCHIVE &nbsp;›&nbsp; LEGACY_RECORD.db &nbsp;›&nbsp; READ_ONLY
            <span className="arc-blink"> ▌</span>
          </div>
          <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:'rgba(197,160,89,0.28)', letterSpacing:'0.1em' }}>1405.SH</div>
        </div>

        <div style={{ padding:'0 2rem 2rem' }}>

          {/* query line */}
          <div style={{ padding:'1rem 0', borderBottom:'1px solid rgba(197,160,89,0.08)', direction:'ltr' }}>
            <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:'rgba(197,160,89,0.35)', marginBottom:5 }}>
              <span style={{ color:'rgba(0,210,130,0.5)' }}>vandidad@archive</span>
              <span style={{ color:'rgba(197,160,89,0.3)' }}>:~$</span>
              <span style={{ color:'rgba(197,160,89,0.55)' }}> query legacy --from 1382 --to 1405 --sort asc</span>
            </div>
            <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:'rgba(0,210,130,0.5)', marginBottom:8 }}>
              ✓ &nbsp;11 records &nbsp;·&nbsp; 2 entities &nbsp;·&nbsp; checksum: A9F2D7C &nbsp;·&nbsp; {time} UTC
            </div>
            <div style={{ display:'flex', gap:16 }}>
              {[['rgba(0,210,180,0.55)','CONCERT'],['rgba(197,160,89,0.55)','CEREMONY'],['rgba(120,160,255,0.55)','EXHIBITION'],['rgba(220,100,100,0.55)','INSTITUTE']].map(([c,l])=>(
                <span key={l} style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9 }}>
                  <span style={{ color:c }}>■ </span>{l}
                </span>
              ))}
            </div>
          </div>

          <div style={{ display:'grid', gridTemplateColumns:'1fr 1px 1fr', gap:'0 2rem', marginTop:'1.4rem' }}>

            {/* Iran */}
            <div>
              <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5, letterSpacing:'0.2em', color:'rgba(197,160,89,0.3)', marginBottom:12, direction:'ltr' }}>
                [ENTITY_01] VANDIDAD_HONAR_PARS · IR
              </div>
              {RECORDS.map((r,i) => (
                <div key={i} className="arc-rec" style={{ display:'grid', gridTemplateColumns:'50px 1px 1fr auto', gap:'0 14px', padding:'9px 4px', borderBottom:'1px solid rgba(197,160,89,0.055)', alignItems:'center' }}>
                  <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:'rgba(197,160,89,0.65)', textAlign:'left' }}>{r.yr}</div>
                  <div style={{ background:'rgba(197,160,89,0.12)', width:1, alignSelf:'stretch' }}/>
                  <div>
                    <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, letterSpacing:'0.18em', color:r.color, display:'block', marginBottom:2 }}>{r.type}</span>
                    <span style={{ fontSize:12.5, color:'rgba(210,225,240,0.85)' }}>{r.fa}</span>
                  </div>
                  <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, color:'rgba(197,160,89,0.2)', whiteSpace:'nowrap' }}>{r.hash}</div>
                </div>
              ))}
            </div>

            {/* divider */}
            <div style={{ background:'linear-gradient(to bottom,transparent,rgba(197,160,89,0.18) 15%,rgba(197,160,89,0.18) 85%,transparent)' }}/>

            {/* Turkey */}
            <div>
              <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5, letterSpacing:'0.2em', color:'rgba(197,160,89,0.3)', marginBottom:12, direction:'ltr' }}>
                [ENTITY_02] VANDIDAD_GROUP · TR
              </div>
              <div style={{ background:'rgba(197,160,89,0.04)', border:'1px solid rgba(197,160,89,0.1)', borderRadius:6, padding:12, marginBottom:14, direction:'ltr' }}>
                <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5, color:'rgba(197,160,89,0.4)', marginBottom:6, letterSpacing:'0.1em' }}>STATUS: ACTIVE · SINCE: 1395.SH · MODE: EXPANDING</div>
                <div style={{ direction: isRtl ? 'rtl' : 'ltr', fontSize:12.5, color:'rgba(210,225,240,0.72)', lineHeight:1.9, fontWeight:300 }}>
                  مدیریت هلدینگ بین‌المللی، سرمایه‌گذاری کلان ساختمانی و نمایندگی انحصاری برندهای برتر معماری جهان از جمله <span style={{ color:'#EDD89A' }}>NEF</span>.
                </div>
              </div>
              <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5, letterSpacing:'0.15em', color:'rgba(197,160,89,0.3)', marginBottom:10, direction:'ltr' }}>DEPLOYED_SYSTEMS // 1405.SH:</div>
              <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
                {SYSTEMS.map((s,i) => (
                  <div key={i} style={{ padding:'10px 12px', border:`1px solid ${s.live ? 'rgba(0,210,130,0.2)' : 'rgba(197,160,89,0.15)'}`, borderRadius:4, background: s.live ? 'rgba(0,210,130,0.04)' : 'transparent' }}>
                    <div style={{ display:'flex', alignItems:'center', gap:8, direction:'ltr', marginBottom:5 }}>
                      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5, letterSpacing:'0.12em', padding:'2px 7px', borderRadius:2, background: s.live ? 'rgba(0,210,130,0.1)' : 'rgba(197,160,89,0.1)', color: s.live ? '#00D282' : '#C5A059', border: `1px solid ${s.live ? 'rgba(0,210,130,0.25)' : 'rgba(197,160,89,0.25)'}` }}>{s.live ? 'LIVE' : 'DEV'}</span>
                      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:11, color:`rgba(240,230,211,${s.live ? 0.85 : 0.5})`, flex:1 }}>{s.id}</span>
                      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:'rgba(197,160,89,0.28)' }}>{s.ver}</span>
                    </div>
                    <div style={{ height:2, background:'rgba(197,160,89,0.1)', borderRadius:1 }}>
                      <div style={{ height:'100%', width:`${s.pct}%`, borderRadius:1, background: s.live ? 'linear-gradient(to right,rgba(0,210,130,0.4),rgba(0,210,130,0.7))' : 'linear-gradient(to right,rgba(197,160,89,0.3),rgba(197,160,89,0.5))' }}/>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:1, background:'rgba(197,160,89,0.08)', borderRadius:6, overflow:'hidden', marginTop:12, border:'1px solid rgba(197,160,89,0.08)' }}>
                {[['20+','EVENTS'],['4','SYSTEMS'],['23','YEARS']].map(([n,l])=>(
                  <div key={l} style={{ background:'#04060F', padding:'11px', textAlign:'center' }}>
                    <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:20, fontWeight:300, color:'#C5A059' }}>{n}</div>
                    <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:7.5, color:'rgba(197,160,89,0.3)', letterSpacing:'0.15em', marginTop:2 }}>{l}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* footer */}
          <div style={{ marginTop:'1.4rem', paddingTop:'1rem', borderTop:'1px solid rgba(197,160,89,0.07)', direction:'ltr', display:'flex', justifyContent:'space-between', alignItems:'center', flexWrap:'wrap', gap:8 }}>
            <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:'rgba(197,160,89,0.2)', letterSpacing:'0.1em' }}>
              END_OF_RECORD · CHECKSUM: A9F2D7C4 · VERIFIED ✓
            </div>
            <div className="arc-pulse" style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:'rgba(197,160,89,0.3)', letterSpacing:'0.08em' }}>
              ● VANDIDAD_ARCHIVE 1405.SH
            </div>
          </div>
        </div>
      </div>
    </motion.section>
  )
}
