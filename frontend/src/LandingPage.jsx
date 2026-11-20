import { ArrowRight, CheckCircle, CloudSun, Leaf, MessageCircle, Store, ScanLine } from 'lucide-react';
import { useEffect } from 'react';

const appPath = '/app';

export default function LandingPage() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const nodes = document.querySelectorAll('.landing-hero, .landing-section, .landing-footer');
    nodes.forEach(node => node.classList.add('reveal-pending'));
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.classList.add('revealed'); observer.unobserve(entry.target); }
    }), { threshold: 0.12 });
    nodes.forEach(node => observer.observe(node));
    return () => observer.disconnect();
  }, []);
  return <div className="landing-shell"><a className="skip-link" href="#landing-main">Skip to content</a>
    <header className="landing-nav">
      <a className="landing-brand" href="/" aria-label="Kisan Mitra home">
        <span className="brandmark"><Leaf/></span>
        <span>Kisan Mitra<small>शेतकरी मित्र</small></span>
      </a>
      <nav aria-label="Main navigation">
        <a href="#how-it-works">How it works</a>
        <a href="#features">Features</a>
        <a className="landing-nav-cta" href={appPath}>Open the app <ArrowRight size={18}/></a>
      </nav>
    </header>

    <main id="landing-main" tabIndex="-1">
      <section className="landing-hero">
        <div className="landing-hero-copy">
          <span className="landing-kicker"><span/> FARM ADVICE, ROOTED IN YOUR PLACE</span>
          <h1>Better farm decisions, closer to home.</h1>
          <p>Get local crop advice, a seven-day weather forecast and nearby mandi prices in Marathi, Hindi or English.</p>
          <div className="landing-actions">
            <a className="landing-primary" href={appPath}>Open Kisan Mitra <ArrowRight size={20}/></a>
            <a className="landing-secondary" href="#how-it-works">How it works</a>
          </div>
          <div className="landing-promise"><CheckCircle size={19}/> Free to use · No account needed</div>
        </div>
        <div className="landing-visual" role="group" aria-label="Kisan Mitra app preview">
          <div className="preview-header"><span className="preview-logo"><Leaf size={20}/></span><b>Kisan Mitra</b><span className="preview-live"><i/> Local farm view</span></div>
          <div className="preview-greeting"><span>☀️</span><div><small>YOUR FARM, TODAY</small><strong>Advice that starts with your district and crop.</strong></div></div>
          <div className="preview-feature preview-green"><span><CloudSun/></span><div><b>Weather at a glance</b><small>See the next seven days</small></div><ArrowRight size={18}/></div>
          <div className="preview-feature preview-cream"><span><Store/></span><div><b>Nearby mandi prices</b><small>Compare market rates</small></div><ArrowRight size={18}/></div>
          <div className="preview-feature preview-white"><span><MessageCircle/></span><div><b>Ask in your language</b><small>Speak or type a question</small></div><ArrowRight size={18}/></div>
          <div className="preview-note"><Leaf size={17}/> Practical information, in one simple place.</div>
        </div>
      </section>

      <section className="landing-section problem-section">
        <div className="section-intro"><span className="landing-kicker">THE CHALLENGE</span><h2>Farm decisions depend on what’s happening nearby.</h2><p>Weather, market prices and crop advice are often scattered across different places and languages.</p></div>
        <div className="problem-grid">
          <article><span className="problem-symbol">☁️</span><h3>Weather changes the plan</h3><p>Rain, heat and wind can affect when it is sensible to spray, irrigate or harvest.</p></article>
          <article><span className="problem-symbol">₹</span><h3>Market rates take effort to compare</h3><p>Nearby mandi prices can be difficult to find and read side by side.</p></article>
          <article><span className="problem-symbol">🌱</span><h3>Advice should be easy to understand</h3><p>Local-language guidance makes useful information easier to act on.</p></article>
        </div>
      </section>

      <section className="landing-section how-section" id="how-it-works">
        <div className="section-intro"><span className="landing-kicker">A SIMPLE START</span><h2>Try it in 3 steps</h2><p>Choose a few farm details, then get information that fits your place and crop.</p></div>
        <div className="steps-grid">
          <article><span className="step-number">01</span><h3>Choose your language and farm</h3><p>Select a district and crop. Your choices stay in your browser.</p></article>
          <article><span className="step-number">02</span><h3>Check today and the week ahead</h3><p>See a short crop recommendation alongside local weather and risk notes.</p></article>
          <article><span className="step-number">03</span><h3>Compare or ask</h3><p>Review nearby mandi prices or ask a question by voice or text.</p></article>
        </div>
      </section>

      <section className="landing-section features-section" id="features">
        <div className="section-intro"><span className="landing-kicker">MADE FOR EVERYDAY FARM DECISIONS</span><h2>Useful information, together.</h2></div>
        <div className="features-grid">
          <article><span className="feature-icon"><Leaf/></span><h3>Today’s crop advice</h3><p>Short guidance informed by weather and available market information.</p></article>
          <article><span className="feature-icon"><CloudSun/></span><h3>Seven-day weather</h3><p>Forecast details and clear notes for rain, heat and wind risks.</p></article>
          <article><span className="feature-icon"><Store/></span><h3>Nearby mandi prices</h3><p>Compare modal, minimum and maximum prices by market.</p></article>
          <article><span className="feature-icon"><MessageCircle/></span><h3>Voice or text questions</h3><p>Ask in your selected language and listen to the response.</p></article>
          <article><span className="feature-icon"><ScanLine/></span><h3>Crop Doctor</h3><p>Share a clear leaf photo to get a possible diagnosis and practical next steps.</p></article>
        </div>
        <div className="landing-bottom-cta"><div><span className="landing-kicker">START WITH YOUR FARM</span><h2>Let’s make today’s decisions clearer.</h2></div><a className="landing-primary" href={appPath}>Open Kisan Mitra <ArrowRight size={20}/></a></div>
      </section>
    </main>

    <footer className="landing-footer"><div className="footer-brand"><span className="brandmark"><Leaf/></span><div><b>Kisan Mitra</b><span>शेतकरी मित्र</span></div></div><div className="footer-copy"><p>AI guidance can be wrong. Ask your local agriculture officer about serious crop problems and all pesticide or fertiliser dosages.</p><p className="footer-credits">Credits: Google Gemini · Open-Meteo · data.gov.in (Agmarknet) · Vercel · Render · Web Speech API</p></div><a href={appPath}>Open the app <ArrowRight size={17}/></a></footer>
  </div>;
}
