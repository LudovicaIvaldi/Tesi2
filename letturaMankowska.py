import json
import numpy as np

class Istanza():
    def __init__(self):
        self.caregiver_servizi = None
        self.paziente_servizi = None
        self.servizi = None
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

        #differenza con toy nelle distanze, non ho la matrice delle distanze ma le coord geografiche x,y
        #devo calcolare la distanza euclidea per trovare la distanza da percorrere fra 2 pazienti
        self.distanze = {}
        self.coord_map = {}
        self.distanzeDaZero = {}
        self.distanzeDict = {}


        self.caregiversPossibili=[]
        #paramentri per il modello manlowska


    def letturaFile(self, nomeFile):
        # Carica il file JSON
        with open(nomeFile+".json", "r") as f:
            data = json.load(f)

        # Estrai tutti gli ID dei pazienti
        patient_ids = [patient["id"] for patient in data["patients"]]
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


        # print(caregiver_patient_lists)
        self.pazientiVisitabili = caregiver_patient_lists


        #solo per i doppi
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


        self.durataVisita = durations_map
        #print(self.durataVisita)

#---------------------------PARTE NUOVA RISPETTO A TOY PER IL CALCOLO DELLE DISTANZE-------------------------------

        central_location = data["central_offices"][0]["location"]

        coord_map = {p["id"]: p["location"] for p in data["patients"]}
        coord_map["0"] = central_location
        coord_map["d"] = central_location
        # Duplicati ereditano le stesse coordinate
        for pid in multi_service_patients:
            coord_map[pid + "'"] = coord_map[pid]

        # Costruzione liste x e y
        x = [coord_map[pid][0] for pid in pazienti_primi]
        y = [coord_map[pid][1] for pid in pazienti_primi]

        n = len(x)
        distanze = np.zeros((n, n))

        # Calcolo distanza euclidea
        for i in range(n):
            for j in range(n):
                distanze[i][j] = round(np.sqrt((x[i] - x[j]) ** 2 + (y[i] - y[j]) ** 2), 3)
        # print("distanz fra i pazienti, matrice con [0 p1 .....d]x[0 p1 .....d] ")
        # print(distanze)
        self.distanze = distanze
        self.coord_map = coord_map  # mi salvo le coordinate

        #dizionario distanze
        # Crea dizionario delle distanze con chiavi stringhe dei pazienti
        distanze_dict = {}
        for i, pid_i in enumerate(pazienti_primi):
            distanze_dict[pid_i] = {}
            for j, pid_j in enumerate(pazienti_primi):
                distanze_dict[pid_i][pid_j] = distanze[i][j]


        self.distanzeDict = distanze_dict
        #print(self.distanzeDict)
#----------------------------------------Fine parte nuova, c'è il dix da zero al fondo-------------------------------------------

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


        self.caregiversPossibili = caregivers_per_patient_dict
        # print(caregivers_per_patient)
        self.caregiversPossibili=caregivers_per_patient_dict


# ---------------------Paramentri mankowska------------------------------------------

        # Crea la lista dei servizi dalla sezione "services"
        self.servizi = [service["id"] for service in data.get("services", [])]

        # Dizionario paziente -> lista di servizi richiesti
        self.paziente_servizi = {}

        for paziente in data.get("patients", []):
            pid = paziente["id"]
            servizi = [req["service"] for req in paziente.get("required_caregivers", [])]
            self.paziente_servizi[pid] = servizi
            self.paziente_servizi["0"]= self.servizi

        self.caregiver_servizi = {
            caregiver["id"]: caregiver["abilities"]
            for caregiver in data["caregivers"]
        }





        #--------------------------CHIAMO FUNZIONI PER CREARE LE DISTANZE DAL MAGAZZINO--------------------------
        self.costruisci_distanze_da_magazzino()
        #print(self.distanzeDaZero)


#-----------------------FUNZIONI PER CALCOLARE LE DISTANZE---------------------------------------

    def calcola_distanza(self, id1, id2):
        x1, y1 = self.coord_map[id1]
        x2, y2 = self.coord_map[id2]
        return round(np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2), 3)

    def costruisci_distanze_da_magazzino(self):
        distanze_zero = {}

        for pid in self.pazientiPrimi:
            if pid != "0":  # saltiamo il magazzino stesso
                distanze_zero[pid] = self.calcola_distanza("0", pid)

        self.distanzeDaZero = distanze_zero







