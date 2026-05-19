import { motion } from 'framer-motion'
import { useLanguage } from '../context/LanguageContext'

const DATA = {
  fa: {
    label: '[ راهکار ]', heading: 'لایه تفکر کسب‌وکار در سال ۲۰۲۶',
    sub: 'حاصل ۴ سال تحقیق بی‌وقفه، تحصیل تجربی و گذراندن دوره‌های تخصصی بین‌المللی در لبه فناوری هوش مصنوعی.',
    cols: [
      { tag: 'TIER 01', title: 'وب‌سایت‌ها', desc: 'ویترین ایستا برای نمایش اطلاعات. فاقد درک، پویایی و توانایی انجام کارهای عملیاتی.', dim: true },
      { tag: 'TIER 02', title: 'اتوماسیون معمولی', desc: 'ربات‌های صلب و خطی. بدون هوش و قدرت انطباق. اگر شرایط تغییر کند کاملاً از کار می‌افتند.', dim: true },
      { tag: 'TIER 03 — AIOS', title: 'سیستم‌عامل اختصاصی', desc: 'کارمند ارشد، رازدان و خودمختار. خودش تحلیل می‌کند، تصمیم می‌گیرد، مذاکره می‌کند و فرآیند را خاتمه می‌دهد.', dim: false },
    ],
    proof: 'شواهد جهانی: دنیا به کدام سمت می‌رود؟',
    proofDesc: 'این یک فرضیه تئوریک نیست؛ Salesforce ساختار نرم‌افزاری خود را به سیستم‌عامل ایجنت‌های خودمختار منتقل کرده است.',
    proofLink: 'SALESFORCE AGENTFORCE →',
  },
  en: {
    label: '[ SOLUTION ]', heading: 'The Enterprise Cognitive Layer (2026)',
    sub: 'The product of 4 years of rigorous research, deep technological integration, and elite international AI certifications.',
    cols: [
      { tag: 'TIER 01', title: 'Websites & Portals', desc: 'Purely static visual interfaces. Completely blind, inert, and incapable of executing real business logic.', dim: true },
      { tag: 'TIER 02', title: 'Legacy Automation', desc: 'Rigid, linear programmatic rules. No reasoning ability. If market conditions shift slightly, they break completely.', dim: true },
      { tag: 'TIER 03 — AIOS', title: 'Bespoke AIOS', desc: 'Not a generic chatbot. An autonomous, secure corporate mind that analyzes, negotiates, decides, and closes operations.', dim: false },
    ],
    proof: 'Global Evidence — Where is the world moving?',
    proofDesc: 'This is not a theoretical assumption. Salesforce has shifted its entire operational architecture to autonomous agentic layers via Agentforce.',
    proofLink: 'EXPLORE SALESFORCE AGENTFORCE →',
  },
  tr: {
    label: '[ ÇÖZÜM ]', heading: 'Kurumsal Yapay Zeka Katmanı (2026)',
    sub: 'Yapay zeka teknolojisinin zirvesinde 4 yıllık araştırma ve uluslararası sertifikaların ürünü.',
    cols: [
      { tag: 'TIER 01', title: 'Web Siteleri', desc: 'Yalnızca bilgi gösterimi için statik arayüzler. İşletme mantığını yürütme yeteneğinden tamamen yoksundur.', dim: true },
      { tag: 'TIER 02', title: 'Geleneksel Otomasyon', desc: 'Katı, doğrusal kurallar. Akıl yürütme gücü yok. Koşullar değişirse tamamen çöker.', dim: true },
      { tag: 'TIER 03 — AIOS', title: 'Özel AIOS', desc: 'Genel bir sohbet robotu değil. Analiz eden, müzakere eden ve süreci otonom olarak sonuçlandıran dijital yönetici.', dim: false },
    ],
    proof: 'Küresel Kanıtlar — Dünya nereye gidiyor?',
    proofDesc: 'Salesforce, yazılım yapısını Agentforce platformu üzerinden otonom ajan katmanlarına taşıdı.',
    proofLink: 'SALESFORCE AGENTFORCE →',
  },
  ar: {
    label: '[ الحل ]', heading: 'طبقة التفكير المؤسسي ٢٠٢٦',
    sub: 'نتاج ٤ سنوات من البحث المستمر والتجارب التقنية والشهادات الدولية المعتمدة في تقنية الذكاء الاصطناعي.',
    cols: [
      { tag: 'TIER 01', title: 'المواقع والواجهات', desc: 'مجرد واجهة ثابتة لعرض المعلومات. تفتقر تماماً إلى القدرة على تنفيذ العمليات التجارية.', dim: true },
      { tag: 'TIER 02', title: 'الأتمتة التقليدية', desc: 'برمجيات صلبة ذات قواعد جامدة. إذا تغيرت ظروف السوق تتوقف تماماً.', dim: true },
      { tag: 'TIER 03 — AIOS', title: 'نظام تشغيل الذكاء الاصطناعي', desc: 'ليس روبوتاً عاماً. موظف تنفيذي رفيع ومستقل يحلل ويفاوض ويتخذ القرار بشكل ذاتي.', dim: false },
    ],
    proof: 'الأدلة العالمية — إلى أين يتجه العالم؟',
    proofDesc: 'نقلت Salesforce نظامها بالكامل إلى طبقات الوكلاء المستقلين عبر منصة Agentforce.',
    proofLink: 'SALESFORCE AGENTFORCE →',
  },
  de: {
    label: '[ LÖSUNG ]', heading: 'Die Unternehmens-KI-Schicht (2026)',
    sub: 'Das Ergebnis von 4 Jahren intensiver Forschung und internationaler KI-Zertifizierungen.',
    cols: [
      { tag: 'TIER 01', title: 'Websites', desc: 'Rein statische Informationsdarstellung. Völlig blind und unfähig, echte Geschäftslogik auszuführen.', dim: true },
      { tag: 'TIER 02', title: 'Legacy-Automatisierung', desc: 'Starre, lineare Regeln. Keine Intelligenz. Bei Marktveränderungen bricht das System zusammen.', dim: true },
      { tag: 'TIER 03 — AIOS', title: 'Maßgeschneidertes AIOS', desc: 'Kein generischer Chatbot. Ein autonomes, sicheres digitales Gehirn das analysiert, verhandelt und abschließt.', dim: false },
    ],
    proof: 'Globale Beweise — Wohin bewegt sich die Welt?',
    proofDesc: 'Salesforce hat seine Architektur auf autonome Agentenschichten über die Agentforce-Plattform umgestellt.',
    proofLink: 'SALESFORCE AGENTFORCE →',
  },
}

export default function AIOSSection() {
  const { lang } = useLanguage()
  const d = DATA[lang] || DATA.fa
  const isRtl = lang === 'fa' || lang === 'ar'

  return (
    <section style={{
      background: 'linear-gradient(180deg,#040810 0%,#060B18 100%)',
      borderTop: '1px solid rgba(255,255,255,0.04)',
      padding: 'clamp(60px,10vh,120px) clamp(20px,6vw,80px)',
      direction: isRtl ? 'rtl' : 'ltr',
    }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>

        <motion.div initial={{ opacity:0,y:20 }} whileInView={{ opacity:1,y:0 }}
          viewport={{ once:true }} transition={{ duration:0.6 }}
          style={{ textAlign:'center', marginBottom:'clamp(40px,7vh,80px)' }}>
          <div style={{ fontFamily:'"Courier New",monospace', fontSize:'11px',
            letterSpacing:'0.25em', color:'rgba(0,242,254,0.5)',
            textTransform:'uppercase', marginBottom:'16px' }}>{d.label}</div>
          <h2 style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
            fontSize:'clamp(1.6rem,3vw,2.8rem)', fontWeight:900,
            color:'#fff', marginBottom:'16px' }}>{d.heading}</h2>
          <p style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
            fontSize:'clamp(0.85rem,1.1vw,1rem)', color:'rgba(180,200,230,0.55)',
            maxWidth:'600px', margin:'0 auto', lineHeight:1.9 }}>{d.sub}</p>
        </motion.div>

        {/* 3 comparison columns */}
        <div style={{ display:'grid',
          gridTemplateColumns:'repeat(auto-fit,minmax(260px,1fr))',
          gap:'20px', marginBottom:'clamp(40px,7vh,70px)' }}>
          {d.cols.map((col, i) => (
            <motion.div key={i}
              initial={{ opacity:0, y:40 }}
              whileInView={{ opacity:1, y:0 }}
              viewport={{ once:true }}
              transition={{ duration:0.6, delay: i*0.15 }}
              style={{
                background: col.dim ? 'rgba(255,255,255,0.02)' : 'rgba(0,242,254,0.04)',
                border: col.dim ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,242,254,0.35)',
                borderRadius:'12px', padding:'clamp(24px,3vh,36px)',
                position:'relative', overflow:'hidden',
                boxShadow: col.dim ? 'none' : '0 0 40px rgba(0,242,254,0.08)',
                animation: col.dim ? 'none' : 'float 4s ease-in-out infinite',
              }}>
              {!col.dim && (
                <div style={{ position:'absolute', top:0, left:0, right:0, height:'2px',
                  background:'linear-gradient(90deg,#00F2FE,#A855F7)' }}/>
              )}
              <div style={{ fontFamily:'"Courier New",monospace', fontSize:'9px',
                letterSpacing:'0.2em', color: col.dim ? 'rgba(255,255,255,0.25)' : '#00F2FE',
                marginBottom:'14px', textTransform:'uppercase' }}>{col.tag}</div>
              <h3 style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
                fontSize:'clamp(1.1rem,1.5vw,1.3rem)', fontWeight:700,
                color: col.dim ? 'rgba(255,255,255,0.5)' : '#fff',
                marginBottom:'12px' }}>{col.title}</h3>
              <p style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
                fontSize:'clamp(0.8rem,1vw,0.9rem)',
                color: col.dim ? 'rgba(180,200,230,0.35)' : 'rgba(180,200,230,0.7)',
                lineHeight:1.8 }}>{col.desc}</p>
            </motion.div>
          ))}
        </div>

        {/* Global proof */}
        <motion.div initial={{ opacity:0,y:30 }} whileInView={{ opacity:1,y:0 }}
          viewport={{ once:true }} transition={{ duration:0.7, delay:0.2 }}
          style={{ background:'rgba(255,255,255,0.02)',
            border:'1px solid rgba(255,255,255,0.06)',
            borderRadius:'12px', padding:'clamp(24px,4vh,40px)',
            textAlign:'center' }}>
          <h4 style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
            fontSize:'clamp(1rem,1.5vw,1.3rem)', fontWeight:700,
            color:'#fff', marginBottom:'12px' }}>{d.proof}</h4>
          <p style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
            fontSize:'clamp(0.8rem,1vw,0.9rem)', color:'rgba(180,200,230,0.55)',
            maxWidth:'700px', margin:'0 auto 20px', lineHeight:1.9 }}>{d.proofDesc}</p>
          <a href="https://www.salesforce.com/agentforce/" target="_blank"
            rel="noopener noreferrer" style={{ fontFamily:'"Courier New",monospace',
              fontSize:'11px', letterSpacing:'0.2em', color:'#00F2FE',
              textDecoration:'none', textTransform:'uppercase',
              borderBottom:'1px solid rgba(0,242,254,0.3)',
              paddingBottom:'2px' }}>{d.proofLink}</a>
        </motion.div>
      </div>
      <style>{`@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}`}</style>
    </section>
  )
}
