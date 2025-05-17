import json
import numpy as np

#c'è il problema che nel toy non ci sono le x e le y delle posizioni ma solo le distanze come matrice
#il problema è che quelle distanze non ci sono per i pazienti primi (risolvibile prendi la stessa distanza che per p)


class IstanzaToy:
    def __init__(self):
        self.pazienti = []
        self.caregivers = []
        self.pazientiDueServizi = []
        self.pazientiDoppi = [] #sono i pazienti con due servizi trasformati con apice '
        self.pazientiPrimi = [] #elenco di tutti i pazienti che possono essere trattati allo stesso modo (1 servizio a testa)

        self.e = {} #tempo di inizi visita ammissibile
        self.l = {} #tempo di fine visita ammissibile


        self.pazientiVisitabili=[] #per ogni k lista con tutti i p che può visitare (creati in base ai servizi erogati da k
                                #e quelli richiesti da p


        self.dmin=[] #solo per i p con 2 servizi intervallo di tempo fra cui eseguire il primo e il secondo servizio
        self.dmax=[] #se devo avere prestazione simultanea di 2 k -> dmin e dmax a 0 (così i t vengono uguali)

        self.durataVisita={}

        self.caregiversPossibili=[] #per ogni p lista dei k che li possono servire in base a s

        self.distanze = [] #matrice di input
        self.distanzeDaZero = {} #prima riga -> da magazzino a pazienti
        self.distanzeDict = {} #per ogni paziente la distanza dagli altri pazienti (peri pazienti doppi è stata presa la stessa
                            #distanza che per il paziente non doppio




    def letturaToy(self,nomeFile):
        # Carico il file JSON
        with open(nomeFile+".json", "r") as f:
            data = json.load(f)

        # Estraggo tutti gli ID dei pazienti
        patient_ids = [patient["id"] for patient in data["patients"]]
        self.pazienti=patient_ids
        # print(f"Pazienti: {patient_ids}")


        # Estraggo tutti gli ID dei caregivers
        caregiver_ids = [caregiver["id"] for caregiver in data["caregivers"]]
        self.caregivers=caregiver_ids
        # print(f"Caregivers: {caregiver_ids}")

        # Lista dei pazienti che richiedono più di un servizio
        multi_service_patients = [patient["id"] for patient in data["patients"] if len(patient["required_caregivers"]) > 1]
        self.pazientiDueServizi=multi_service_patients
        # print(f"Pazienti con 2 servizi: {multi_service_patients}")
        
        # lista con i duplicati dei pazienti che ricevono 2 servizi -> con apice '
        # Questi sono da considerare proprio come dei pazienti in più da servire (a cui viene erogato 1 solo servizio)
        self.pazientiDoppi = []
        for p in self.pazientiDueServizi:
            self.pazientiDoppi.append(p + "'")
        # print(self.pazientiDoppi)

        #set dei pazienti con i doppi
        # lista pazienti_primi con ' aggiunto per multi-service
        pazienti_primi = patient_ids + [pid + "'" for pid in multi_service_patients]
        pazienti_primi = [pid for pid in pazienti_primi]
        self.pazientiPrimi=pazienti_primi
        # print(f"Set P': {pazienti_primi}")


        # prendi l ed e
        e_dict_raw = {patient["id"]: patient["time_window"][0] for patient in data["patients"]}
        l_dict_raw = {patient["id"]: patient["time_window"][1] for patient in data["patients"]}

        # Per i doppi con ', erediti lo stesso e e l del paziente base
        for patient_id in self.pazientiDueServizi:
            e_dict_raw[patient_id + "'"] = e_dict_raw[patient_id]
            l_dict_raw[patient_id + "'"] = l_dict_raw[patient_id]

        # Costruisci i dizionari finali e l
        self.e = {pid: e_dict_raw[pid] for pid in pazienti_primi}
        self.l = {pid: l_dict_raw[pid] for pid in pazienti_primi}
        # print("e =", self.e)
        # print("l =", self.l)

        # Step 1: Mappa pazienti → singoli servizi (split se necessario)
        patient_service_map = [] #tupla con id paziente e servizio

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
            # Aggiungiamo "0" all'inizio perchè tutti i k devono servire 0 che è il magazzino
            complete_list = ["0"] + eligible
            caregiver_patient_lists.append(complete_list)


        self.pazientiVisitabili=caregiver_patient_lists
        # print(caregiver_patient_lists)


        #solo per i doppi finestra di tempo in cui eseguire il secondo servizio
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

        # Crea mappa durate per ogni ID (split inclusi)
        durations_map = {}

        for patient in data["patients"]:
            base_id = patient["id"]
            required = patient["required_caregivers"]

            if len(required) == 1:
                durations_map[base_id] = required[0]["duration"]
            else:
                # paziente splittato in due -> devi prendere il tempo del secondo servizio
                durations_map[base_id] = required[0]["duration"]
                durations_map[base_id + "'"] = required[1]["duration"]


        self.durataVisita = durations_map

        # Distanze tra pazienti: ignora la prima riga che rappresenta le distanze dal magazzino
        raw_matrix = data["distances"][1:]

        # Verifica di consistenza -> mi serve perchè gli altri dataset sono costruiti diversamente per le distanze
        if len(raw_matrix) != len(self.pazientiPrimi):
            raise ValueError("Mismatch tra numero di righe nella matrice e pazienti attesi.")

        # Crea dizionario di dizionari per le distanze
        distanze_dict = {}
        for i, pid_i in enumerate(self.pazientiPrimi):
            distanze_dict[pid_i] = {}
            row = raw_matrix[i][1:]  # Ignora il primo elemento della riga (distanza con 0 magazzino)
            for j, pid_j in enumerate(self.pazientiPrimi):
                distanze_dict[pid_i][pid_j] = row[j]


        self.distanzeDict = distanze_dict
        # print(self.distanzeDict)

        # Diz servizio per ogni paziente (anche doppi)
        #per ogni p metto s che richiede
        #i p che hanno due servizi hanno la copia p' che richiede il secondo servizio
        service_per_patient = {}

        for patient in data["patients"]:
            base_id = patient["id"]
            required = patient["required_caregivers"]

            if len(required) == 1:
                service_per_patient[base_id] = required[0]["service"]
            else:
                service_per_patient[base_id] = required[0]["service"]
                service_per_patient[base_id + "'"] = required[1]["service"]

        # Diz caregiver elenco servizi che sa fare
        caregiver_abilities = {
            caregiver["id"]: set(caregiver["abilities"])
            for caregiver in data["caregivers"]
        }

        # Dizionario caregivers compatibili per ciascun paziente in pazienti_primi
        caregivers_per_patient_dict = {}

        for pid in pazienti_primi:
            if pid in ["0"]:
                caregivers_per_patient_dict[pid] = caregiver_ids  # Tutti possono teoricamente andare al magazzino
            else:
                servizio = service_per_patient[pid]
                compatibili = [cid for cid, abilita in caregiver_abilities.items() if servizio in abilita]
                caregivers_per_patient_dict[pid] = compatibili


        self.caregiversPossibili = caregivers_per_patient_dict
        #print(self.caregiversPossibili)

        #distanze da magazzino
        # Crea dizionario distanzeDaZero prendendo la prima riga della matrice delle distanze
        prima_riga = data["distances"][0][1:]  # Ignora il primo elemento (distanza 0→0)
        if len(prima_riga) != len(self.pazientiPrimi):
            raise ValueError("Mismatch tra numero di elementi nella prima riga e pazienti attesi.") #mi serve perchè
            #gli altri dataset daranno errrore

        self.distanzeDaZero = dict(zip(self.pazientiPrimi, prima_riga))
        #print (self.distanzeDaZero)

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

