import React from "react";

// Apple‑style one‑page landing for Clara Law (clean, airy, high‑contrast spacing)
// Tailwind CSS utilities only. Inline SVG logo (círculo + triângulo) na paleta da marca.
// Seções: Navbar • Hero • Valor • Fluxos (DoNotPay‑style) • Como funciona • Rotas regulatórias • MEI/PME & Licitações • Métrica R$ • FAQ • Footer

export default function ClaraLawLanding() {
  return (
    <main className="min-h-screen bg-white text-slate-900">
      {/* Navbar */}
      <header className="sticky top-0 z-30 backdrop-blur border-b border-slate-200/80 bg-white/70">
        <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between">
          <LogoMark />
          <nav className="hidden md:flex items-center gap-6 text-sm">
            <a className="hover:opacity-80" href="#fluxos">Fluxos</a>
            <a className="hover:opacity-80" href="#como-funciona">Como funciona</a>
            <a className="hover:opacity-80" href="#regulatorio">Rotas</a>
            <a className="hover:opacity-80" href="#licitacoes">MEI/PME</a>
            <a className="hover:opacity-80" href="#faq">FAQ</a>
          </nav>
          <div className="flex items-center gap-2">
            <a href="#cta" className="px-4 py-2 rounded-xl border border-slate-200 hover:bg-slate-50">Entrar</a>
            <a href="#cta" className="px-4 py-2 rounded-xl bg-[#A8D8F0] text-slate-900 font-semibold hover:brightness-95">Começar grátis</a>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-6xl px-4 pt-16 pb-10">
        <div className="grid md:grid-cols-2 gap-10 items-center">
          <div>
            <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight leading-[1.1]">
              Inteligência para um <span className="text-[#A8D8F0]">mundo mais claro</span>.
            </h1>
            <p className="mt-5 text-lg text-slate-600 max-w-[50ch]">
              Dinheiro que escapa → a Clara recupera ou evita. Documentos confusos → a Clara traduz e orienta.
              Você entende, decide e economiza.
            </p>
            <div className="mt-7 flex flex-col sm:flex-row gap-3">
              <a id="cta" href="#fluxos" className="px-5 py-3 rounded-2xl bg-[#D4AF37] text-white font-semibold hover:brightness-95">
                Iniciar um caso agora
              </a>
              <a href="#como-funciona" className="px-5 py-3 rounded-2xl border border-slate-200 hover:bg-slate-50">
                Ver como funciona
              </a>
            </div>
            <div className="mt-6 text-sm text-slate-500">
              Sem juridiquês • Fluxos guiados (sim/não + anexos) • Gera cartas e protocolos prontos
            </div>
          </div>
          <div className="relative">
            <div className="absolute -inset-8 bg-[#A8D8F0]/20 blur-3xl rounded-full" />
            <div className="relative rounded-3xl border border-slate-200 p-6 bg-white shadow-[0_10px_40px_-15px_rgba(2,6,23,0.15)]">
              <HeroCard />
            </div>
          </div>
        </div>
      </section>

      {/* Promessa de valor */}
      <section className="mx-auto max-w-6xl px-4 py-6">
        <div className="grid md:grid-cols-3 gap-6">
          <ValueTile title="Recupere ou evite perdas" desc="A Clara encontra cobranças indevidas e calcula quanto você economiza todo mês."/>
          <ValueTile title="Tradução jurídica em minutos" desc="Contrato confuso? A Clara explica em linguagem simples e aponta próximos passos."/>
          <ValueTile title="Rotas oficiais do Brasil" desc="Procon, Senacon, Bacen, Anatel, ANAC, ANS, Consumidor.gov e JEC – passo a passo real."/>
        </div>
      </section>

      {/* Fluxos (DoNotPay‑style BR) */}
      <section id="fluxos" className="mx-auto max-w-6xl px-4 py-14">
        <h2 className="text-3xl md:text-4xl font-bold">Casos campeões (clique e resolva)</h2>
        <p className="text-slate-600 mt-2">Perguntas simples, anexos opcionais, documento pronto para envio.</p>
        <div className="mt-8 grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <FlowCard title="Cancelar assinaturas" items={["Academia/Apps", "TV/Telefonia"]} cta="Gerar pedido de cancelamento"/>
          <FlowCard title="Cobrança indevida" items={["Banco/Cartão", "Consignado"]} cta="Contestar e pedir estorno"/>
          <FlowCard title="Negociar faturas" items={["Energia/Água", "Telefonia"]} cta="Propor desconto/parcelas (CET)"/>
          <FlowCard title="Dinheiro esquecido" items={["Valores a Receber (BACEN)", "Contas antigas"]} cta="Gerar solicitação de saque"/>
          <FlowCard title="Transporte aéreo" items={["Atraso/Cancelamento", "Extravio de bagagem"]} cta="Reclamar via ANAC + companhia"/>
          <FlowCard title="Proteção de dados (LGPD)" items={["Excluir/Restringir dados", "Vazamento"]} cta="Solicitar providências ao DPO"/>
        </div>
      </section>

      {/* Como funciona */}
      <section id="como-funciona" className="mx-auto max-w-6xl px-4 py-14">
        <h2 className="text-3xl md:text-4xl font-bold">Como funciona</h2>
        <div className="mt-8 grid md:grid-cols-3 gap-6">
          <Step num="1" title="Responda sim/não">
            A Clara guia com perguntas claras. Se tiver comprovantes, faça upload.
          </Step>
          <Step num="2" title="Veja o cálculo em R$">
            Economia/recuperação estimada (CET, juros, multas, dano material). Transparente e didático.
          </Step>
          <Step num="3" title="Gere e envie">
            Carta, reclamação, notificação e protocolo. Rotas oficiais e prazos de resposta.
          </Step>
        </div>
      </section>

      {/* Regulatorio */}
      <section id="regulatorio" className="mx-auto max-w-6xl px-4 py-14">
        <h2 className="text-3xl md:text-4xl font-bold">Rotas oficiais do Brasil</h2>
        <p className="text-slate-600 mt-2">A Clara prepara tudo para os canais corretos, com base legal simples e prazos.</p>
        <div className="mt-6 flex flex-wrap gap-2">
          {["Procon","Senacon","Consumidor.gov","Bacen","Anatel","ANAC","ANS","JEC"].map(x => (
            <span key={x} className="px-3 py-1 rounded-full border border-slate-200 bg-slate-50">{x}</span>
          ))}
        </div>
      </section>

      {/* MEI/PME & Licitações */}
      <section id="licitacoes" className="mx-auto max-w-6xl px-4 py-14">
        <div className="grid md:grid-cols-2 gap-10 items-center">
          <div>
            <h2 className="text-3xl md:text-4xl font-bold">MEI/PME e Licitações</h2>
            <ul className="mt-4 space-y-2 text-slate-700">
              <li>• Kit anti‑cilada contratual: maquininha, marketplace, aluguel, SaaS.</li>
              <li>• Pré‑licitação para iniciantes: checklist de habilitação e leitura em “português humano”.</li>
              <li>• Simuladores financeiros: CET, renegociação, plano de pagamento.</li>
            </ul>
            <div className="mt-6 flex gap-3">
              <a href="#cta" className="px-5 py-3 rounded-2xl bg-[#D4AF37] text-white font-semibold hover:brightness-95">Começar agora</a>
              <a href="#faq" className="px-5 py-3 rounded-2xl border border-slate-200 hover:bg-slate-50">Saiba mais</a>
            </div>
          </div>
          <div className="rounded-3xl border border-slate-200 p-6 bg-white shadow-[0_10px_40px_-15px_rgba(2,6,23,0.15)]">
            <SavingsWidget />
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="mx-auto max-w-6xl px-4 py-14">
        <h2 className="text-3xl md:text-4xl font-bold">Perguntas frequentes</h2>
        <div className="mt-6 grid md:grid-cols-2 gap-6">
          <Faq q="A Clara substitui advogados?" a="Não. É uma mentora digital que orienta com base em regras e dados. Para casos complexos, indicamos atendimento profissional."/>
          <Faq q="Quanto custa?" a="Plano gratuito com 1–2 casos. Premium entre R$9 e R$19/mês com fluxos ilimitados e histórico."/>
          <Faq q="Funciona no WhatsApp?" a="Sim. Tire foto do contrato/conta e a Clara guia o passo a passo."/>
          <Faq q="E a privacidade?" a="Transparência e controle. Você decide o que enviar, quando e para onde."/>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200">
        <div className="mx-auto max-w-6xl px-4 py-10 grid md:grid-cols-2 gap-6 items-center">
          <div className="flex items-center gap-3"><LogoMark size={22}/><span className="text-sm text-slate-600">© Clara Law 2025</span></div>
          <div className="text-sm text-slate-500 md:text-right">Inteligência para um mundo mais claro.</div>
        </div>
      </footer>
    </main>
  );
}

function LogoMark({ size = 28 }) {
  return (
    <div className="flex items-center gap-2">
      <svg width={size} height={size} viewBox="0 0 96 96" aria-hidden>
        <circle cx="48" cy="48" r="42" fill="none" stroke="#D4AF37" strokeWidth="6" />
        {/* triângulo equilátero */}
        <path d="M48 22 L75 68 H21 Z" fill="none" stroke="#D4AF37" strokeWidth="6" strokeLinejoin="round" />
      </svg>
      <span className="font-semibold tracking-wide text-[#A8D8F0]">CLARA LAW</span>
    </div>
  );
}

function ValueTile({ title, desc }){
  return (
    <div className="rounded-3xl border border-slate-200 p-6 bg-white shadow-sm">
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="mt-2 text-slate-600 text-sm">{desc}</p>
    </div>
  );
}

function FlowCard({ title, items = [], cta }){
  return (
    <div className="rounded-3xl border border-slate-200 p-6 bg-white hover:shadow-md transition">
      <h3 className="text-lg font-semibold">{title}</h3>
      <ul className="mt-2 text-slate-600 text-sm space-y-1">
        {items.map((x) => <li key={x}>• {x}</li>)}
      </ul>
      <a href="#cta" className="mt-4 inline-flex px-4 py-2 rounded-xl bg-[#A8D8F0] text-slate-900 font-semibold hover:brightness-95">{cta}</a>
    </div>
  );
}

function Step({ num, title, children }){
  return (
    <div className="rounded-3xl border border-slate-200 p-6 bg-white">
      <div className="w-8 h-8 rounded-full bg-[#A8D8F0] text-slate-900 grid place-items-center font-bold">{num}</div>
      <h3 className="mt-3 text-lg font-semibold">{title}</h3>
      <p className="mt-2 text-slate-600 text-sm">{children}</p>
    </div>
  );
}

function SavingsWidget(){
  return (
    <div>
      <h3 className="text-lg font-semibold">Economia estimada</h3>
      <p className="text-slate-600 text-sm mt-1">A Clara mede em R$: por caso e no total acumulado.</p>
      <div className="mt-5 rounded-2xl bg-slate-50 border border-slate-200 p-5">
        <div className="flex items-end gap-2"><span className="text-4xl font-extrabold">R$ 1.240</span><span className="text-slate-500 mb-1 text-sm">mês</span></div>
        <div className="text-slate-500 text-xs mt-1">Exemplo somando: estorno de cobrança + renegociação de fatura + cancelamento de apps.</div>
        <div className="mt-4 h-2 bg-slate-200 rounded-full overflow-hidden">
          <div className="h-full bg-[#D4AF37] w-2/3" />
        </div>
      </div>
      <div className="mt-4 flex gap-2">
        <span className="px-3 py-1 rounded-full border border-slate-200 bg-white text-xs">CET calculado</span>
        <span className="px-3 py-1 rounded-full border border-slate-200 bg-white text-xs">Comparador de juros</span>
        <span className="px-3 py-1 rounded-full border border-slate-200 bg-white text-xs">Plano de pagamento</span>
      </div>
    </div>
  );
}

function HeroCard(){
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-emerald-500"/>
        <p className="text-sm text-slate-600">Fluxo: Cancelar assinatura</p>
      </div>
      <div className="rounded-2xl border border-slate-200 p-4">
        <p className="text-sm">Você quer cancelar qual serviço?</p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
          <button className="px-3 py-2 rounded-xl border hover:bg-slate-50">Streaming</button>
          <button className="px-3 py-2 rounded-xl border hover:bg-slate-50">Telefonia</button>
          <button className="px-3 py-2 rounded-xl border hover:bg-slate-50">Academia</button>
          <button className="px-3 py-2 rounded-xl border hover:bg-slate-50">Outros</button>
        </div>
        <div className="mt-4 text-xs text-slate-500">Anexe comprovante (opcional)</div>
        <div className="mt-2 flex items-center justify-between bg-slate-50 border rounded-xl px-3 py-2 text-xs">
          <span>Comprovante.pdf</span>
          <span className="text-slate-400">42 KB</span>
        </div>
      </div>
      <div className="rounded-2xl border border-slate-200 p-4">
        <p className="text-sm">Economia estimada</p>
        <div className="mt-1 text-2xl font-extrabold">R$ 89/mês</div>
        <div className="mt-2 text-xs text-slate-500">Base legal: direito de cancelamento e não imposição de obstáculos abusivos (CDC).</div>
      </div>
      <button className="w-full px-4 py-3 rounded-2xl bg-[#D4AF37] text-white font-semibold hover:brightness-95">Gerar pedido de cancelamento</button>
    </div>
  );
}

function Faq({ q, a }){
  return (
    <div className="rounded-3xl border border-slate-200 p-6 bg-white">
      <h3 className="font-semibold">{q}</h3>
      <p className="mt-2 text-slate-600 text-sm">{a}</p>
    </div>
  );
}









