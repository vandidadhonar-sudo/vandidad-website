import { motion } from 'framer-motion'
import { useLanguage } from '../context/LanguageContext'

const DATA = {
  fa: {
    label: '[ مسئله ]',
    heading: 'مسئله امروز کسب‌وکارها',
    sub: 'اکثر مجموعه‌ها فعال‌اند، اما هوشمند نیستند. در ظاهر همه چیز دارند، در عمل سیستم ندارند.',
    cards: [
      { tag: '01 / DECISION MAKING', title: 'اتکا به تجربه شخصی', desc: 'تصمیم‌های استراتژیک بر اساس حدس، خطای انسانی و شهود شخصی گرفته می‌شود، نه تحلیل داده‌های زنده.' },
      { tag: '02 / SALES STRUCTURE', title: 'وابستگی فروش به افراد', desc: 'فرآیند فروش به اشخاص وابسته است؛ با رفتن یک فرد، بخش بزرگی از بازدهی بیزنس سقوط می‌کند.' },
      { tag: '03 / MARKETING INFRA', title: 'بازاریابی واکنشی و جزیره‌ای', desc: 'اقدامات مارکتینگ پراکنده، پرهزینه و واکنشی است و خط سیر مشخصی برای صید هوشمند بازار ندارد.' },
      { tag: '04 / DATA SILOS', title: 'حبس و اتلاف داده‌ها', desc: 'داده‌های حیاتی وجود دارند، اما هیچ مغز متفکری برای تحلیل و تبدیل آن‌ها به ثروت وجود ندارد.' },
    ]
  },
  en: {
    label: '[ PROBLEM ]',
    heading: 'The Modern Business Crisis',
    sub: 'Most enterprises are active, but not intelligent. They appear to have everything; in reality they lack a real system.',
    cards: [
      { tag: '01 / DECISION MAKING', title: 'Personal Intuition Reliance', desc: 'Strategic decisions are built on guesswork and personal intuition rather than autonomous real-time data analysis.' },
      { tag: '02 / SALES STRUCTURE', title: 'Human-Dependent Sales', desc: 'Sales operations rely completely on individuals. When a key person leaves, the entire revenue baseline collapses.' },
      { tag: '03 / MARKETING INFRA', title: 'Reactive Marketing Silos', desc: 'Marketing is fragmented, costly, and reactive — with no clear path for intelligent market acquisition.' },
      { tag: '04 / DATA SILOS', title: 'Stagnant Data Baselines', desc: 'Vital data exists but lays frozen with no centralized brain to analyze and turn it into financial architecture.' },
    ]
  },
  tr: {
    label: '[ SORUN ]',
    heading: 'Modern İşletmelerin Krizi',
    sub: 'Çoğu işletme aktif, ancak akıldan yoksun. Görünüşte her şeye sahipler; gerçekte sistem yok.',
    cards: [
      { tag: '01 / DECISION MAKING', title: 'Kişisel Sezgi Bağımlılığı', desc: 'Stratejik kararlar canlı veri analizi yerine tahmin ve kişisel sezgiye dayanır.' },
      { tag: '02 / SALES STRUCTURE', title: 'İnsana Bağımlı Satış', desc: 'Satış süreçleri tamamen kişilere bağlıdır. Kritik biri ayrıldığında tüm gelir yapısı çöker.' },
      { tag: '03 / MARKETING INFRA', title: 'Reaktif Pazarlama', desc: 'Pazarlama dağınık, maliyetli ve reaktiftir — akıllı müşteri kazanımı için net rota yoktur.' },
      { tag: '04 / DATA SILOS', title: 'Veri Hapsi', desc: 'Hayati veriler var ama bunları finansal mimariye dönüştürecek merkezi bir beyin yok.' },
    ]
  },
  ar: {
    label: '[ المشكلة ]',
    heading: 'أزمة الشركات المعاصرة',
    sub: 'معظم المؤسسات نشطة لكنها تفتقر إلى الذكاء. في الظاهر تمتلك كل شيء؛ في الواقع تفتقر إلى نظام.',
    cards: [
      { tag: '01 / DECISION MAKING', title: 'الاعتماد على الحدس الشخصي', desc: 'القرارات الاستراتيجية تُبنى على التخمين بدلاً من تحليل البيانات الحية.' },
      { tag: '02 / SALES STRUCTURE', title: 'اعتماد المبيعات على الأفراد', desc: 'عمليات المبيعات تعتمد على الأشخاص. عندما يغادر موظف رئيسي، ينهار الهيكل الإيرادي.' },
      { tag: '03 / MARKETING INFRA', title: 'التسويق الانفعالي المجزأ', desc: 'النشاط التسويقي مشتت ومكلف وانفعالي — بلا مسار واضح لجذب السوق بذكاء.' },
      { tag: '04 / DATA SILOS', title: 'احتباس البيانات', desc: 'البيانات الحيوية موجودة لكن لا يوجد عقل مركزي لتحليلها وتحويلها إلى ثروة.' },
    ]
  },
  de: {
    label: '[ PROBLEM ]',
    heading: 'Die moderne Unternehmenskrise',
    sub: 'Die meisten Unternehmen sind aktiv, aber nicht intelligent. Sie haben alles — aber kein echtes System.',
    cards: [
      { tag: '01 / DECISION MAKING', title: 'Abhängigkeit von Intuition', desc: 'Strategische Entscheidungen basieren auf Vermutungen statt auf Echtzeit-Datenanalyse.' },
      { tag: '02 / SALES STRUCTURE', title: 'Menschenabhängiger Vertrieb', desc: 'Der Vertrieb hängt von Einzelpersonen ab. Wenn jemand geht, bricht der Umsatz ein.' },
      { tag: '03 / MARKETING INFRA', title: 'Reaktives Marketing', desc: 'Marketing ist fragmentiert, teuer und reaktiv — ohne klaren Pfad zur intelligenten Kundengewinnung.' },
      { tag: '04 / DATA SILOS', title: 'Datengefangenschaft', desc: 'Wichtige Daten existieren, aber es gibt kein zentrales Gehirn, um sie in Wert umzuwandeln.' },
    ]
  },
}

const cardVariants = {
  hidden: { opacity: 0, y: 40 },
  visible: (i) => ({
    opacity: 1, y: 0,
    transition: { duration: 0.6, delay: i * 0.15, ease: [0.25, 0.46, 0.45, 0.94] }
  })
}

export default function ProblemSection() {
  const { lang } = useLanguage()
  const d = DATA[lang] || DATA.fa
  const isRtl = lang === 'fa' || lang === 'ar'

  return (
    <section style={{
      background: '#040810',
      borderTop: '1px solid rgba(255,255,255,0.05)',
      padding: 'clamp(60px,10vh,120px) clamp(20px,6vw,80px)',
      direction: isRtl ? 'rtl' : 'ltr',
    }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>

        {/* Top label */}
        <motion.div
          initial={{ opacity: 0, x: isRtl ? 30 : -30 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          style={{
            fontFamily: '"Courier New",monospace',
            fontSize: '11px', letterSpacing: '0.25em',
            color: 'rgba(0,242,254,0.5)', marginBottom: '20px',
            textTransform: 'uppercase',
          }}
        >{d.label}</motion.div>

        {/* Layout: heading left, cards right */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: 'clamp(30px,5vw,60px)',
          alignItems: 'start',
        }}>

          {/* Heading column */}
          <motion.div
            initial={{ opacity: 0, x: isRtl ? 40 : -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, ease: 'easeOut' }}
            style={{ position: 'sticky', top: '100px' }}
          >
            <h2 style={{
              fontFamily: 'Vazirmatn,Inter,sans-serif',
              fontSize: 'clamp(1.6rem,3vw,2.8rem)',
              fontWeight: 900, color: '#fff',
              lineHeight: 1.3, marginBottom: '20px',
            }}>{d.heading}</h2>

            <p style={{
              fontFamily: 'Vazirmatn,Inter,sans-serif',
              fontSize: 'clamp(0.85rem,1.1vw,1rem)',
              color: 'rgba(180,200,230,0.6)',
              lineHeight: 1.9, fontWeight: 300,
            }}>{d.sub}</p>

            {/* Decorative line */}
            <motion.div
              initial={{ scaleX: 0 }}
              whileInView={{ scaleX: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8, delay: 0.3 }}
              style={{
                height: '2px', width: '60px',
                background: 'linear-gradient(90deg,#00F2FE,#A855F7)',
                marginTop: '28px',
                transformOrigin: isRtl ? 'right' : 'left',
              }}
            />
          </motion.div>

          {/* Cards column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {d.cards.map((card, i) => (
              <motion.div
                key={i}
                custom={i}
                variants={cardVariants}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                whileHover={{ scale: 1.015, transition: { duration: 0.2 } }}
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.07)',
                  borderRadius: '8px',
                  padding: 'clamp(18px,3vh,28px) clamp(18px,2.5vw,28px)',
                  cursor: 'default',
                  position: 'relative',
                  overflow: 'hidden',
                }}
              >
                {/* Hover glow line */}
                <motion.div
                  initial={{ opacity: 0 }}
                  whileHover={{ opacity: 1 }}
                  style={{
                    position: 'absolute',
                    top: 0,
                    [isRtl ? 'right' : 'left']: 0,
                    width: '3px', height: '100%',
                    background: 'linear-gradient(to bottom,#00F2FE,#A855F7)',
                    borderRadius: '4px 0 0 4px',
                  }}
                />

                <div style={{
                  fontFamily: '"Courier New",monospace',
                  fontSize: '10px', letterSpacing: '0.2em',
                  color: '#00F2FE', marginBottom: '10px',
                  textTransform: 'uppercase',
                }}>{card.tag}</div>

                <h3 style={{
                  fontFamily: 'Vazirmatn,Inter,sans-serif',
                  fontSize: 'clamp(1rem,1.4vw,1.2rem)',
                  fontWeight: 700, color: '#fff',
                  marginBottom: '8px',
                }}>{card.title}</h3>

                <p style={{
                  fontFamily: 'Vazirmatn,Inter,sans-serif',
                  fontSize: 'clamp(0.8rem,1vw,0.9rem)',
                  color: 'rgba(180,200,230,0.6)',
                  lineHeight: 1.8, fontWeight: 300,
                }}>{card.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
