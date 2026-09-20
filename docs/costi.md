# Costi

L'obiettivo dichiarato era tenere l'app accesa spendendo il meno possibile.
Questa pagina spiega da dove viene ogni voce e quali leve esistono.

> I prezzi sono indicativi, in EUR, per la regione Sweden Central, e cambiano
> nel tempo. Verifica sempre con il
> [calcolatore Azure](https://azure.microsoft.com/pricing/calculator/).

## Stima per uso personale

Ipotesi: un utente, 2-3 sessioni a settimana, una ventina di richieste per
sessione, qualche annuncio analizzato al mese.

| Servizio | Piano | Costo mensile |
|---|---|---|
| Static Web Apps | Free | **0** |
| Container Apps | Consumption, min 0 repliche | **0** (dentro il piano gratuito) |
| Storage Account | Standard LRS, < 1 GB | **~0,05** |
| Log Analytics | PerGB2018, quota 0,2 GB/giorno | **0** (dentro i 5 GB gratuiti) |
| AI Foundry (gpt-4o-mini) | GlobalStandard, a consumo | **~0,10 – 0,50** |
| Container Registry | non creato (si usa GHCR) | **0** |
| **Totale** | | **circa 0,20 – 0,60 EUR/mese** |

In pratica la spesa è dominata dai token dell'AI, e resta sotto l'euro se non
si fa un uso intensivo della generazione.

## Da dove viene lo zero

### Container Apps: il piano gratuito mensile

Il profilo Consumption include ogni mese, per sottoscrizione:

* 180.000 vCPU-secondi
* 360.000 GiB-secondi
* 2 milioni di richieste

Con `cpu = 0.25` e `memory = 0.5Gi`, i 180.000 vCPU-secondi corrispondono a
circa **200 ore di container acceso**. Con `min_replicas = 0` il container si
spegne dopo qualche minuto di inattività, quindi un uso personale resta
largamente dentro la soglia.

Il prezzo del cold start è di qualche secondo sulla prima richiesta dopo una
pausa. Se dà fastidio, `min_replicas = 1` lo elimina ma tiene il container
sempre acceso: circa **720 ore al mese**, cioè fuori dal piano gratuito, per
**~10-15 EUR/mese**. È la leva che pesa di più sul totale.

### Static Web Apps Free

Include 100 GB di banda al mese, HTTPS, dominio personalizzato e build da
GitHub. Per un'app personale non si arriva mai al limite. Il piano Free non
supporta il collegamento di un backend gestito, ed è la ragione per cui il
frontend chiama la Container App direttamente via CORS invece di passare da
`/api` sulla stessa origine.

### Log Analytics: dove il costo può esplodere

È l'unica voce che può sorprendere. Dopo i 5 GB mensili gratuiti si pagano
circa 2,30 EUR/GB, e un'applicazione che entra in un loop di errori può
scrivere gigabyte in poche ore.

Per questo `log_daily_quota_gb` è impostata a 0,2 GB: superata la quota,
l'ingestione si ferma fino al giorno successivo. Si perdono log, non soldi.

### AI Foundry

gpt-4o-mini costa indicativamente 0,15 USD per milione di token in input e
0,60 per milione in output. Le chiamate dell'app:

| Operazione | Token stimati | Costo per chiamata |
|---|---|---|
| Analisi di un annuncio | ~2.000 in, ~800 out | ~0,0008 EUR |
| Scheda azienda | ~1.500 in, ~700 out | ~0,0006 EUR |
| Generazione del piano | ~3.000 in, ~1.200 out | ~0,0012 EUR |
| Nuovo argomento + 3 quiz | ~600 in, ~1.500 out | ~0,0010 EUR |
| Revisione del CV | ~5.000 in, ~1.500 out | ~0,0017 EUR |
| Revisione del codice | ~1.500 in, ~800 out | ~0,0007 EUR |

Preparare un colloquio da zero, cioè analisi più azienda più piano più CV più
qualche revisione di codice, costa dell'ordine di **mezzo centesimo**.

`ai_capacity = 10` limita il deployment a 10.000 token al minuto: non è un tetto
di spesa ma di velocità, ed è comunque una difesa utile contro i consumi
anomali.

## Le leve, in ordine di impatto

| Leva | Risparmio | Costo della scelta |
|---|---|---|
| `min_replicas = 0` (default) | ~10-15 EUR/mese | Qualche secondo di cold start |
| GHCR invece di ACR (default) | ~4,60 EUR/mese | Il package deve essere pubblico |
| `log_daily_quota_gb = 0.2` | Evita picchi da decine di EUR | Log troncati nei giorni peggiori |
| `enable_ai = false` | Azzera i token | L'app resta usabile ma con le sole euristiche |
| `ai_model_name` più economico | Proporzionale | Qualità delle generazioni inferiore |
| Table Storage invece di Cosmos | ~20 EUR/mese | Query meno espressive |

## Tenere d'occhio la spesa

Il Terraform crea un budget con due avvisi via email: all'80% del previsto e
alla proiezione del 100%.

```hcl
monthly_budget_eur = 15
budget_alert_email = "tu@esempio.it"
```

È un avviso, non un blocco: Azure non spegne nulla al superamento. Per
controllare a mano:

```bash
az consumption usage list --start-date 2026-09-01 --end-date 2026-09-30 \
  --query "[].{risorsa:instanceName, costo:pretaxCost}" -o table
```

## Se davvero deve costare zero

Metti `enable_ai = false`. L'app funziona: analizza l'annuncio con il
dizionario di tecnologie, costruisce il piano con lo scoring deterministico,
serve le 146 domande del catalogo e valuta il CV sulla copertura delle parole
chiave. Perdi la scheda azienda generata, la revisione ragionata del CV e del
codice, e la creazione automatica di nuovi argomenti — che però puoi comunque
scrivere a mano dalla pagina Argomenti.
