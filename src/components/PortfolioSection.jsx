import { useState } from 'react'
import { motion } from 'framer-motion'
import { useLanguage } from '../context/LanguageContext'

const DATA = {
  fa: {
    label:'[ کارنامه ]', heading:'کارنامه عینی و ویترین نوآوری‌ها',
    sub:'نمونه‌های توسعه‌یافته و در حال پیاده‌سازی متصل به بازار واقعی.',
    products:[
      { tag:'Ecosystem Product', title:'VANTA Sales OS & CRM', desc:'سیستم‌عامل خودمختار ارکستراسیون ایجنت‌های هوشمند برای فایلینگ اختصاصی، CRM و پیش‌برد فروش در صنایع بزرگ و املاک.' },
      { tag:'Legal Tech', title:'Vanta Legal OS', desc:'پلتفرم پیشگام جهت هوشمندسازی مناسبات حقوقی وکلا، پایش چک‌لیست‌های قضایی و ارائه مشاوره قانونی دقیق.' },
      { tag:'Behavioral AI', title:'PANAH (پناه)', desc:'دستیار هوشمند مشاوره روانشناسی مبتنی بر رویکردهای علمی، پروتکل‌های درمانی شخصی‌سازی شده و درک عمیق رفتاری.' },
      { tag:'EdTech AI Agent', title:'Professor P (پروفسور پی)', desc:'سیستم فوق‌پیشرفته آموزش زبان انگلیسی به صورت تعاملی از بنیان تا آمادگی آزمون‌های بین‌المللی IELTS.' },
    ],
    openTitle:'انعطافِ بی‌مرز برای صنف شما',
    openDesc:'این زنجیره پایان ندارد. سیستم‌عامل هوشمند شما، دقیقاً متناسب با شناسنامه و گره‌های تجاری صنف خودتان از نو معماری می‌شود.',
  },
  en: {
    label:'[ PORTFOLIO ]', heading:'Proven Operational Deployments',
    sub:'Bespoke high-performance intelligent frameworks engineered for real-world industries.',
    products:[
      { tag:'Ecosystem Product', title:'VANTA Sales OS & CRM', desc:'Autonomous multi-agent ecosystem for proprietary filing, CRM orchestration, and executive real-estate sales closing.' },
      { tag:'Legal Tech', title:'Vanta Legal OS', desc:'Revolutionary cognitive layer to streamline legal frameworks, monitor risk checklists, and provide judicial guidance.' },
      { tag:'Behavioral AI', title:'PANAH', desc:'Advanced psychological counseling AI built on validated clinical modalities, tailored evaluation protocols, and synthetic emotional intelligence.' },
      { tag:'EdTech AI Agent', title:'Professor P', desc:'Sophisticated interactive English language simulation engine engineered for conversational mastery up to IELTS standards.' },
    ],
    openTitle:'Infinite Adaptability Across Industries',
    openDesc:'This structural lineage is open-ended. Your AIOS layer is custom-built to match your unique brand DNA, whatever your industry.',
  },
  tr: {
    label:'[ PORTFÖY ]', heading:'Kanıtlanmış Operasyonel Başarılar',
    sub:'Gerçek pazar ihtiyaçları için otonom olarak geliştirilen yapay zeka projeleri.',
    products:[
      { tag:'Ecosystem Product', title:'VANTA Sales OS & CRM', desc:'Büyük endüstriler için özel dosyalama otonomisi, CRM yönetimi ve akıllı satış kapatma sistemi.' },
      { tag:'Legal Tech', title:'Vanta Legal OS', desc:'Avukatların hukuki süreçlerini akıllı hale getiren ve risk analizleri yapan öncü platform.' },
      { tag:'Behavioral AI', title:'PANAH', desc:'Bilimsel protokollere dayalı akıllı psikolojik danışmanlık ajanı.' },
      { tag:'EdTech AI Agent', title:'Professor P', desc:'Temel seviyeden IELTS standartlarına kadar tam etkileşimli İngilizce dil simülasyon motoru.' },
    ],
    openTitle:'Sektörünüz İçin Sınırsız Esneklik',
    openDesc:'Bu ekosistem ucu açıktır. Akıllı işletim sisteminiz markanızın kimliğine göre sıfırdan tasarlanır.',
  },
  ar: {
    label:'[ المشاريع ]', heading:'المشاريع المنفذة والأنظمة القائمة',
    sub:'نماذج حية من العقول الرقمية المصممة لخدمة قطاعات تجارية حقيقية.',
    products:[
      { tag:'Ecosystem Product', title:'VANTA Sales OS & CRM', desc:'نظام تشغيل متكامل لأتمتة الأرشفة العقارية وإدارة بيانات CRM وإغلاق المبيعات الكبرى.' },
      { tag:'Legal Tech', title:'Vanta Legal OS', desc:'منصة رائدة لأتمتة العمليات القانونية ومراقبة قوائم المخاطر القضائية بدقة.' },
      { tag:'Behavioral AI', title:'PANAH', desc:'مساعد ذكي للاستشارات النفسية مبني على بروتوكولات علمية معتمدة.' },
      { tag:'EdTech AI Agent', title:'Professor P', desc:'محاكي فائق لتعليم اللغة الإنجليزية من البداية حتى مستويات IELTS.' },
    ],
    openTitle:'مرونة لا نهائية لقطاعك التجاري',
    openDesc:'هذه المنظومة مفتوحة الخطوط. نظامك الذكي يُصمم خصيصاً ليتوافق مع هوية عملك الفريدة.',
  },
  de: {
    label:'[ PORTFOLIO ]', heading:'Bewährte operative Einsätze',
    sub:'Maßgeschneiderte hochleistungsfähige KI-Frameworks für reale Branchen.',
    products:[
      { tag:'Ecosystem Product', title:'VANTA Sales OS & CRM', desc:'Autonomes Multi-Agenten-Ökosystem für proprietäres Filing, CRM-Orchestrierung und Immobilien-Vertrieb.' },
      { tag:'Legal Tech', title:'Vanta Legal OS', desc:'Revolutionäre kognitive Schicht zur Optimierung rechtlicher Rahmenbedingungen und Risikoüberwachung.' },
      { tag:'Behavioral AI', title:'PANAH', desc:'Fortschrittlicher psychologischer Beratungs-KI auf Basis validierter klinischer Modalitäten.' },
      { tag:'EdTech AI Agent', title:'Professor P', desc:'Ausgefeilte interaktive Englisch-Simulations-Engine bis hin zu IELTS-Standards.' },
    ],
    openTitle:'Unbegrenzte Anpassungsfähigkeit',
    openDesc:'Ihr AIOS-Layer wird individuell nach Ihrer Marken-DNA aufgebaut, egal in welcher Branche.',
  },
}

function TiltCard({ children, style }) {
  const [tilt, setTilt] = useState({ x:0, y:0, shine:{ x:50, y:50 } })

  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect()
    const x = ((e.clientY - r.top) / r.height - 0.5) * 14
    const y = ((e.clientX - r.left) / r.width - 0.5) * 14
    const sx = ((e.clientX - r.left) / r.width) * 100
    const sy = ((e.clientY - r.top) / r.height) * 100
    setTilt({ x:-x, y, shine:{ x:sx, y:sy } })
  }
  const onLeave = () => setTilt({ x:0, y:0, shine:{ x:50, y:50 } })

  return (
    <div onMouseMove={onMove} onMouseLeave={onLeave} style={{
      transform: `perspective(700px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
      transition: 'transform 0.15s ease',
      position: 'relative', ...style,
    }}>
      <div style={{
        position:'absolute', inset:0, borderRadius:'inherit', pointerEvents:'none',
        background: `radial-gradient(circle at ${tilt.shine.x}% ${tilt.shine.y}%, rgba(0,242,254,0.07) 0%, transparent 60%)`,
        transition: 'background 0.15s',
      }}/>
      {children}
    </div>
  )
}

export default function PortfolioSection() {
  const { lang } = useLanguage()
  const d = DATA[lang] || DATA.fa
  const isRtl = lang === 'fa' || lang === 'ar'

  return (
    <section style={{
      background:'#050A1E', borderTop:'1px solid rgba(255,255,255,0.04)',
      padding:'clamp(60px,10vh,120px) clamp(20px,6vw,80px)',
      direction: isRtl ? 'rtl' : 'ltr',
    }}>
      <div style={{ maxWidth:'1200px', margin:'0 auto' }}>

        <motion.div initial={{ opacity:0,y:20 }} whileInView={{ opacity:1,y:0 }}
          viewport={{ once:true }} transition={{ duration:0.6 }}
          style={{ marginBottom:'clamp(36px,6vh,64px)' }}>
          <div style={{ fontFamily:'"Courier New",monospace', fontSize:'11px',
            letterSpacing:'0.25em', color:'rgba(0,242,254,0.5)',
            textTransform:'uppercase', marginBottom:'14px' }}>{d.label}</div>
          <h2 style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
            fontSize:'clamp(1.6rem,3vw,2.8rem)', fontWeight:900,
            color:'#fff', marginBottom:'12px' }}>{d.heading}</h2>
          <p style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
            fontSize:'clamp(0.85rem,1.1vw,1rem)', color:'rgba(180,200,230,0.55)',
            lineHeight:1.9 }}>{d.sub}</p>
        </motion.div>

        <div style={{ display:'grid',
          gridTemplateColumns:'repeat(auto-fit,minmax(280px,1fr))',
          gap:'20px', marginBottom:'20px' }}>
          {d.products.map((p, i) => (
            <motion.div key={i}
              initial={{ opacity:0, y:40 }}
              whileInView={{ opacity:1, y:0 }}
              viewport={{ once:true }}
              transition={{ duration:0.6, delay: i*0.12 }}>
              <TiltCard style={{
                background:'rgba(255,255,255,0.03)',
                border:'1px solid rgba(255,255,255,0.07)',
                borderRadius:'10px',
                padding:'clamp(20px,3vh,32px)',
                height:'100%',
              }}>
                <div style={{ fontFamily:'"Courier New",monospace', fontSize:'9px',
                  letterSpacing:'0.2em', color:'#A855F7',
                  textTransform:'uppercase', marginBottom:'12px' }}>{p.tag}</div>
                <h3 style={{ fontFamily:'"Courier New",Inter,sans-serif',
                  fontSize:'clamp(1rem,1.4vw,1.2rem)', fontWeight:700,
                  color:'#fff', marginBottom:'10px', letterSpacing:'-0.01em' }}>{p.title}</h3>
                <p style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
                  fontSize:'clamp(0.8rem,1vw,0.88rem)',
                  color:'rgba(180,200,230,0.6)', lineHeight:1.85 }}>{p.desc}</p>
              </TiltCard>
            </motion.div>
          ))}
        </div>

        {/* Open invitation */}
        <motion.div initial={{ opacity:0,y:30 }} whileInView={{ opacity:1,y:0 }}
          viewport={{ once:true }} transition={{ duration:0.7, delay:0.3 }}
          style={{ background:'rgba(168,85,247,0.04)',
            border:'1px dashed rgba(168,85,247,0.25)',
            borderRadius:'10px', padding:'clamp(24px,4vh,40px)',
            textAlign:'center' }}>
          <h4 style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
            fontSize:'clamp(1rem,1.5vw,1.2rem)', fontWeight:700,
            color:'#fff', marginBottom:'12px' }}>{d.openTitle}</h4>
          <p style={{ fontFamily:'Vazirmatn,Inter,sans-serif',
            fontSize:'clamp(0.8rem,1vw,0.9rem)', color:'rgba(180,200,230,0.55)',
            maxWidth:'700px', margin:'0 auto', lineHeight:2 }}>{d.openDesc}</p>
        </motion.div>
      </div>
    </section>
  )
}
