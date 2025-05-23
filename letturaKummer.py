import json
import numpy as np

class IstanzaK():
    def __init__(self):

        #la differenza è nelle distanze, non solo calcolate in modo euclideo con le posizioni x e y (che comunque sono
        #date nel data_set quindi ho lasciato la mappa, ma c'è una matrice con le distanze reali fra quelle coordinate
        #essendo reali la matrice non è simmetrica

        #il problema che mi fa dover cambiare anche il modello è che non essendo simmetrica non posso usare la
        #stessa distanza di andata e ritorno al magazzino

        #ogni paziente ha una andata -> distanzeDaZero
        #e un ritorno messo nel distanzeDict con un nodo aggiuntivo 0

        #l'influenza nel modello riguarda la funzione obbiettivo, perchè nel calcolo della distanza minima percorsa
        #non posso usare distanzeDaZero al "rovescio" ma devo usare un nuovo dizionario

        #cambia anche la print finale tanto non ho le soluzioni con i 3 costi separati ma solo il valore di z


        self.pazienti = []
        self.caregivers = []
        self.pazientiDueServizi = []
        self.pazientiDoppi = []
        self.pazientiPrimi = []
        self.e = {}
        self.l = {}
        self.pazientiVisitabili = []
        self.dmin = {}
        self.dmax = {}
        self.durataVisita = {}

        self.distanze = {}
        self.distanzeDaZero = {}
        self.coord_map = {}
        self.distanzeDict = {} #cambia questo dove ho per ogni p il nodo 0 che rappresenta la distanza di ritorno al magazzino

        self.caregiversPossibili=[]

    def letturaKummer(self, nomeFile):
        # Carica il file JSON
        with open(nomeFile, "r") as f:
            data = json.load(f)

        # Estrai tutti gli ID dei pazienti
        patient_ids = [patient["id"] for patient in data["patients"]]
        # Stampa lista pazienti
        self.pazienti=patient_ids
        # print(f"Pazienti: {patient_ids}")


        # Estrai tutti gli ID dei caregivers
        caregiver_ids = [caregiver["id"] for caregiver in data["caregivers"]]
        self.caregivers=caregiver_ids
        # print(f"Caregivers: {caregiver_ids}")

        # Lista dei pazienti che richiedono più di un servizio
        multi_service_patients = [patient["id"] for patient in data["patients"] if len(patient["required_caregivers"]) > 1]
        self.pazientiDueServizi=multi_service_patients
        # print(f"Pazienti con 2 servizi: {multi_service_patients}")

        #lista con i duplicati dei pazienti che ricevono 2 servizi -> con pedice
        self.pazientiDoppi=[]
        for p in self.pazientiDueServizi:
            self.pazientiDoppi.append(p+"'")
        # print(self.pazientiDoppi)

        #set dei pazienti con i doppi
        # Costruzione della lista pazienti_primi con ' aggiunto per multi-service
        pazienti_primi = patient_ids + [pid + "'" for pid in multi_service_patients if pid != "d"]
        # Rimuovi eventuali "d" duplicati e metti "d" alla fine
        pazienti_primi = [pid for pid in pazienti_primi if pid != "d"]
        self.pazientiPrimi=pazienti_primi
        # print(f"Set P': {pazienti_primi}")

        #prendi l ed e
        e_dict_raw = {patient["id"]: patient["time_window"][0] for patient in data["patients"]}
        l_dict_raw = {patient["id"]: patient["time_window"][1] for patient in data["patients"]}

        # Per i doppi con ', erediti lo stesso e e l del paziente base
        for patient_id in self.pazientiDueServizi:
            e_dict_raw[patient_id + "'"] = e_dict_raw[patient_id]
            l_dict_raw[patient_id + "'"] = l_dict_raw[patient_id]


        # Costruisci i dizionari finali e l
        self.e = {pid: e_dict_raw[pid] for pid in pazienti_primi}
        self.l = {pid: l_dict_raw[pid] for pid in pazienti_primi}
        #print("e =", self.e)
        #print("l =", self.l)


        # Step 1: Mappa pazienti → singoli servizi (split se necessario)
        patient_service_map = []

        for patient in data["patients"]:
            base_id = patient["id"]
            services = patient["required_caregivers"]

            for i, serv in enumerate(services):
                pid = base_id if i == 0 else base_id + "'"
                service = serv["service"]
                patient_service_map.append((pid, service))

        # Step 2: Lista di liste dei pazienti servibili da ciascun caregiver
        caregiver_patient_lists = []

        for caregiver in data["caregivers"]:
            abilities = caregiver["abilities"]
            eligible = [
                pid for (pid, service) in patient_service_map if service in abilities
            ]
            # Aggiungiamo "0" all'inizio
            complete_list = ["0"] + eligible
            caregiver_patient_lists.append(complete_list)

        # Output finale
        # print("Per ogni caregivers i pazienti che può visitare (0 e d sono il magazzino da cui devono partire e arrivare):")
        # print(caregiver_patient_lists)
        self.pazientiVisitabili = caregiver_patient_lists


        #li sto completando solo per i doppi, poi da vedere se vanno fatti per tutti
        dmin = []
        dmax = []

        for patient in data["patients"]:
            if len(patient["required_caregivers"]) > 1:
                sync = patient.get("synchronization", {})
                if sync.get("type") == "sequential":
                    dmin.append(sync["distance"][0])
                    dmax.append(sync["distance"][1])
                elif sync.get("type") == "simultaneous":
                    dmin.append(0)
                    dmax.append(0)
        # print(f"dmin: {dmin}")
        # print(f"dmax: {dmax}")
        self.dmin = dmin
        self.dmax = dmax
        # print(self.dmin)
        # print(self.dmax)

        # Crea mappa durate per ogni ID (split inclusi)
        durations_map = {}

        for patient in data["patients"]:
            base_id = patient["id"]
            required = patient["required_caregivers"]

            if len(required) == 1:
                durations_map[base_id] = required[0]["duration"]
            else:
                # paziente splittato in due
                durations_map[base_id] = required[0]["duration"]
                durations_map[base_id + "'"] = required[1]["duration"]

        # Assegna direttamente la mappa come dizionario
        self.durataVisita = durations_map
        #print(self.durataVisita)

#------------------------------PARTE NUOVA PER LE DISTANZE DALLA MATRICE-----------------------------------------------

        # Ricava la lista pazienti originali (senza doppi)
        pazienti_base = [p["id"] for p in data["patients"]]

        # Prendi la matrice delle distanze
        matrice_distanze = data["distances"]

        # Dizionario distanzeDaZero
        distanze_zero = {}
        for i, pid in enumerate(pazienti_base):
            distanze_zero[pid] = matrice_distanze[0][i + 1]  # salta il primo elemento (0->0)
            if pid + "'" in self.pazientiPrimi:
                distanze_zero[pid + "'"] = matrice_distanze[0][i + 1]  # stesso valore del base per i doppi con '

        self.distanzeDaZero = distanze_zero

        # Costruisci distanzeDict (includendo anche distanza verso "0")
        distanze_dict = {}

        for i, id1 in enumerate(pazienti_base):
            riga = matrice_distanze[i + 1]

            # Inizializza il dizionario per id1 e id1'
            distanze_dict[id1] = {}
            if id1 + "'" in self.pazientiPrimi:
                distanze_dict[id1 + "'"] = {}

            for j, id2 in enumerate(pazienti_base):
                dist = riga[j + 1]  # colonna j+1 (salta 0 che è distanza da 0)

                # id1 → id2
                distanze_dict[id1][id2] = dist
                if id2 + "'" in self.pazientiPrimi:
                    distanze_dict[id1][id2 + "'"] = dist
                if id1 + "'" in self.pazientiPrimi:
                    distanze_dict[id1 + "'"][id2] = dist
                    if id2 + "'" in self.pazientiPrimi:
                        distanze_dict[id1 + "'"][id2 + "'"] = dist

            # Gestione distanza da id1 a "0"
            dist_verso_zero = riga[0]
            distanze_dict[id1]["0"] = dist_verso_zero
            if id1 + "'" in self.pazientiPrimi:
                distanze_dict[id1 + "'"]["0"] = dist_verso_zero

        self.distanzeDict = distanze_dict

#---------------------------------------Fine parte nuova--------------------------------------------------------------

        # Step 1: Crea mappa servizio per ogni paziente (anche doppi)
        service_per_patient = {}

        for patient in data["patients"]:
            base_id = patient["id"]
            required = patient["required_caregivers"]

            if len(required) == 1:
                service_per_patient[base_id] = required[0]["service"]
            else:
                service_per_patient[base_id] = required[0]["service"]
                service_per_patient[base_id + "'"] = required[1]["service"]

        # Step 2: Crea mappa caregiver → set(servizi che può offrire)
        caregiver_abilities = {
            caregiver["id"]: set(caregiver["abilities"])
            for caregiver in data["caregivers"]
        }

        # Step 3: Dizionario caregivers compatibili per ciascun paziente in pazienti_primi
        caregivers_per_patient_dict = {}

        for pid in pazienti_primi:
            if pid in ["0", "d"]:
                caregivers_per_patient_dict[pid] = caregiver_ids  # Tutti possono teoricamente andare al magazzino
            else:
                servizio = service_per_patient[pid]
                compatibili = [cid for cid, abilita in caregiver_abilities.items() if servizio in abilita]
                caregivers_per_patient_dict[pid] = compatibili

        # Assegna al dizionario finale
        self.caregiversPossibili = caregivers_per_patient_dict

        # Output finale
        # print("Per ogni paziente i caregivers che lo pososno servire (primo e ultimo sono il magazzino (servibile da tutti o da nessuno?):")
        # print(caregivers_per_patient)
        self.caregiversPossibili=caregivers_per_patient_dict


        #________________parte per modello 2_______________________________
        # ---------------------Paramentri mankowska------------------------------------------

        # Crea la lista dei servizi dalla sezione "services"
        self.servizi = [service["id"] for service in data.get("services", [])]

        # Dizionario paziente -> lista di servizi richiesti
        self.paziente_servizi = {}

        for paziente in data.get("patients", []):
            pid = paziente["id"]
            servizi = [req["service"] for req in paziente.get("required_caregivers", [])]
            self.paziente_servizi[pid] = servizi
            self.paziente_servizi["0"] = self.servizi

        self.caregiver_servizi = {
            caregiver["id"]: caregiver["abilities"]
            for caregiver in data["caregivers"]
        }

        # Elenco dei servizi disponibili
        all_services = [service["id"] for service in data["services"]]

        # Dizionario per i pazienti
        self.ris = {}
        for patient in data["patients"]:
            required = {s: 0 for s in all_services}
            for req in patient["required_caregivers"]:
                required[req["service"]] = 1
            self.ris[patient["id"]] = required

        self.ris["0"] = {s: 1 for s in self.servizi}

        # Dizionario per i caregiver
        self.avs = {}
        for caregiver in data["caregivers"]:
            abilities = {s: 0 for s in all_services}
            for service in caregiver["abilities"]:
                abilities[service] = 1
            self.avs[caregiver["id"]] = abilities

        # delta dei 2 servizi
        self.dictMin = {}
        self.dictMax = {}

        for patient in data["patients"]:
            sync = patient.get("synchronization")
            if sync:
                pid = patient["id"]
                if sync.get("type") == "sequential" and "distance" in sync:
                    self.dictMin[pid] = sync["distance"][0]
                    self.dictMax[pid] = sync["distance"][1]
                elif sync.get("type") == "simultaneous":
                    self.dictMin[pid] = 0
                    self.dictMax[pid] = 0

        # Estrazione delle informazioni rilevanti
        patients = data["patients"]
        caregivers = data["caregivers"]

        # Costruzione di una mappa caregiver -> abilità (insieme di servizi)
        caregiver_abilities = {
            caregiver["id"]: set(caregiver["abilities"])
            for caregiver in caregivers
        }

        # Costruzione della mappa paziente -> caregiver compatibili
        self.patient_caregiver_map = {}

        for patient in patients:
            patient_id = patient["id"]
            required_services = {req["service"] for req in patient["required_caregivers"]}

            compatible_caregivers = [
                caregiver_id
                for caregiver_id, abilities in caregiver_abilities.items()
                if not required_services.isdisjoint(abilities)  # almeno un servizio in comune
            ]

            self.patient_caregiver_map[patient_id] = compatible_caregivers
            self.patient_caregiver_map["0"] = [k for k in self.caregivers]

        # Estrai caregivers e patients
        caregivers = data["caregivers"]
        patients = data["patients"]

        # Costruisci la mappa dei pazienti visitabili per ciascun caregiver
        self.mappa_pazienti_visitabili = {}

        for caregiver in caregivers:
            cid = caregiver["id"]
            abilita = set(caregiver["abilities"])
            pazienti_visitabili = []
            for paziente in patients:
                servizi_richiesti = {rc["service"] for rc in paziente["required_caregivers"]}
                if abilita & servizi_richiesti:
                    pazienti_visitabili.append(paziente["id"])
            self.mappa_pazienti_visitabili[cid] = pazienti_visitabili + ["0"]


