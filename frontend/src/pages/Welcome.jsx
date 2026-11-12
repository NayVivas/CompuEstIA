import Icon from "../components/Icon";

function StructuralIllustration() {
  return (
    <svg viewBox="0 0 760 500" role="img" aria-label="Ilustración técnica de una estructura de hormigón armado" className="welcome-structure">
      <defs>
        <linearGradient id="structureGlow" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#69e0d1" />
          <stop offset="1" stopColor="#43a8e9" />
        </linearGradient>
        <linearGradient id="concrete" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#d9e8f2" stopOpacity=".22" />
          <stop offset="1" stopColor="#7da5bd" stopOpacity=".07" />
        </linearGradient>
        <filter id="softGlow"><feGaussianBlur stdDeviation="5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <g fill="none" stroke="#8ab7cf" strokeOpacity=".13" strokeWidth="1">
        {Array.from({length:11},(_,i)=><path key={`h${i}`} d={`M55 ${90+i*32}H705`} />)}
        {Array.from({length:15},(_,i)=><path key={`v${i}`} d={`M${70+i*44} 55V430`} />)}
      </g>
      <g stroke="url(#structureGlow)" strokeWidth="2.2" strokeLinejoin="round" fill="url(#concrete)">
        {/* zapatas */}
        <path d="M105 374l85-35 90 34-86 39z" />
        <path d="M194 412v-22l86-39v23z" />
        <path d="M105 374v-21l85-35 90 34v21" />
        <path d="M470 374l82-34 94 34-84 40z" />
        <path d="M552 414v-22l94-40v22z" />
        <path d="M470 374v-22l82-34 94 34v22" />
        {/* pedestals */}
        <path d="M159 342V227l38-17v116z" />
        <path d="M197 326V210l39 17v116z" />
        <path d="M159 227l38 17 39-17-39-17z" />
        <path d="M523 342V227l39-17v116z" />
        <path d="M562 326V210l39 17v116z" />
        <path d="M523 227l39 17 39-17-39-17z" />
        {/* vigas de riostra */}
        <path d="M197 247l365 0 39 18-365 0z" />
        <path d="M236 265v-18l-39-18v18z" />
        <path d="M601 265v-18l-39-18v18z" />
        {/* columnas */}
        <path d="M177 211V95l40-18v116z" />
        <path d="M217 193V77l39 18v116z" />
        <path d="M177 95l40 18 39-18-39-18z" />
        <path d="M541 211V95l40-18v116z" />
        <path d="M581 193V77l39 18v116z" />
        <path d="M541 95l40 18 39-18-39-18z" />
        {/* viga superior */}
        <path d="M217 112l364 0 39 18-364 0z" />
        <path d="M256 130v-18l-39-18v18z" />
        <path d="M620 130v-18l-39-18v18z" />
      </g>
      {/* armaduras */}
      <g fill="none" stroke="#b7f5eb" strokeWidth="1.5" strokeOpacity=".8">
        {Array.from({length:5},(_,i)=><path key={`r1${i}`} d={`M${183+i*8} 90V205`} />)}
        {Array.from({length:5},(_,i)=><path key={`r2${i}`} d={`M${547+i*8} 90V205`} />)}
        {Array.from({length:4},(_,i)=><path key={`p1${i}`} d={`M${165+i*8} 228V340`} />)}
        {Array.from({length:4},(_,i)=><path key={`p2${i}`} d={`M${529+i*8} 228V340`} />)}
        <path d="M172 105h73M172 125h73M172 145h73M172 165h73M172 185h73" />
        <path d="M536 105h73M536 125h73M536 145h73M536 165h73M536 185h73" />
      </g>
      <g fill="#7ee5d7" filter="url(#softGlow)">
        <circle cx="197" cy="77" r="4"/><circle cx="581" cy="77" r="4"/>
        <circle cx="197" cy="244" r="3"/><circle cx="562" cy="244" r="3"/>
      </g>
      <g fill="none" stroke="#72d8d0" strokeWidth="1.3" strokeDasharray="5 7" opacity=".65">
        <path d="M90 430H675" /><path d="M380 55V445" />
      </g>
      <g fill="#b7d5e5" fontFamily="Arial, sans-serif" fontSize="12" letterSpacing="2" opacity=".7">
        <text x="72" y="455">FUNDACIONES</text><text x="324" y="455">ESTRUCTURA</text><text x="590" y="455">COLUMNA</text>
      </g>
    </svg>
  );
}

export default function Welcome({ onEnter }) {
  return (
    <main className="welcome-screen">
      <div className="welcome-grid" aria-hidden="true" />
      <div className="welcome-orb welcome-orb-one" aria-hidden="true" />
      <div className="welcome-orb welcome-orb-two" aria-hidden="true" />

      <div className="welcome-shell">
        <header className="welcome-topbar">
          <div className="welcome-brand">
            <div className="welcome-brand-mark"><Icon name="building" size={25} /></div>
            <div>
              <div className="welcome-brand-name">CómputoEst<span>IA</span></div>
              <div className="welcome-brand-caption">INGENIERÍA CIVIL · CIENCIA DE DATOS</div>
            </div>
          </div>
          <div className="welcome-version"><span /> PLATAFORMA DE ANÁLISIS ESTRUCTURAL</div>
        </header>

        <section className="welcome-hero">
          <div className="welcome-copy">
            <div className="welcome-eyebrow"><span /> INGENIERÍA INTELIGENTE</div>
            <h1>De los planos<br />a los <em>datos.</em></h1>
            <p className="welcome-lead">
              Una plataforma que transforma documentación estructural en información organizada,
              revisable y cuantificable.
            </p>
            <div className="welcome-capabilities">
              <div><Icon name="file" size={17} /><span>Lectura documental</span></div>
              <div><Icon name="scan" size={17} /><span>Extracción y revisión</span></div>
              <div><Icon name="barChart" size={17} /><span>Cómputo métrico</span></div>
            </div>
            <button type="button" className="welcome-enter" onClick={onEnter}>
              Ingresar a la plataforma <Icon name="arrowRight" size={18} />
            </button>
            <p className="welcome-note"><Icon name="shield" size={14} /> Herramienta de asistencia técnica con validación profesional</p>
          </div>

          <div className="welcome-visual">
            <div className="welcome-visual-label"><span className="welcome-live-dot" /> MODELO ESTRUCTURAL · VISTA CONCEPTUAL</div>
            <StructuralIllustration />
            <div className="welcome-visual-footer">
              <span>01 / DOCUMENTACIÓN</span><span>02 / ANÁLISIS</span><span>03 / CÓMPUTO</span>
            </div>
            <div className="welcome-float-card welcome-float-top"><Icon name="layers" size={16}/><span>Elementos estructurales</span><strong>01—04</strong></div>
            <div className="welcome-float-card welcome-float-bottom"><span className="welcome-float-indicator"/><span>Procesamiento inteligente</span><strong>ACTIVO</strong></div>
          </div>
        </section>

        <footer className="welcome-footer">
          <span>CÓMPUTOESTIA</span>
          <span>INTELIGENCIA ARTIFICIAL APLICADA AL CÓMPUTO MÉTRICO ESTRUCTURAL</span>
          <span>VERSIÓN DE DEMOSTRACIÓN</span>
        </footer>
      </div>
    </main>
  );
}
