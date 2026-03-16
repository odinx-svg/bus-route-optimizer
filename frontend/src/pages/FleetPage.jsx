import React, { useEffect, useMemo, useState } from 'react';
import { Building2, Bus, Download, FileText, MapPin, Pencil, Phone, Plus, Save, Trash2, Upload, User, X } from 'lucide-react';
import { notifications } from '../services/notifications';
import {
  commitFleetImport,
  createFleetDriver,
  createFleetVehicle,
  deleteFleetDriver,
  fetchFleetDrivers,
  deleteFleetVehicle,
  fetchVehicleWeeklyPlan,
  fetchFleetVehicles,
  previewFleetImport,
  updateFleetDriver,
  updateVehicleDriverAssignments,
  updateFleetVehicle,
} from '../services/fleetService';

const EMPTY_FORM = {
  vehicle_code: '',
  plate: '',
  brand: '',
  model: '',
  year: '',
  seats_min: '',
  seats_max: '',
  status: 'active',
  fuel_type: 'diesel',
  accessibility: false,
  mileage_km: '',
  notes: '',
  gps_provider: '',
  gps_external_id: '',
  documents: [],
};

const STATUS_LABEL = { active: 'Activo', maintenance: 'Taller', inactive: 'Inactivo' };
const DETAIL_TABS = [
  { id: 'data', label: 'Datos' },
  { id: 'drivers', label: 'Conductores' },
  { id: 'documents', label: 'Documentos' },
  { id: 'gps', label: 'GPS' },
  { id: 'weekly_plan', label: 'Plan semanal' },
];

const DAY_LABELS = { L: 'Lunes', M: 'Martes', Mc: 'Miercoles', X: 'Jueves', V: 'Viernes' };
const DRIVER_CHANNEL_LABELS = { manual: 'Manual', whatsapp: 'WhatsApp', telegram: 'Telegram', call: 'Llamada' };
const DRIVER_DAY_ORDER = ['default', 'L', 'M', 'Mc', 'X', 'V'];
const EMPTY_DRIVER_FORM = {
  full_name: '',
  phone: '',
  email: '',
  preferred_channel: 'manual',
  whatsapp_phone: '',
  telegram_chat_id: '',
  status: 'active',
  notes: '',
};

const minuteToLabel = (value) => {
  const safe = Number(value || 0);
  const hours = Math.floor(safe / 60);
  const minutes = safe % 60;
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
};

const buildDriverAssignmentDraft = (vehicle) => {
  const mapping = { default_driver_id: '', days: { L: '', M: '', Mc: '', X: '', V: '' } };
  (vehicle?.driver_assignments || []).forEach((assignment) => {
    const dayCode = String(assignment?.day_code || '').trim();
    if (dayCode === 'default') {
      mapping.default_driver_id = String(assignment?.driver_id || '').trim();
    } else if (mapping.days[dayCode] !== undefined) {
      mapping.days[dayCode] = String(assignment?.driver_id || '').trim();
    }
  });
  return mapping;
};

const toPayload = (form) => ({
  vehicle_code: String(form.vehicle_code || '').trim(),
  plate: String(form.plate || '').trim(),
  brand: String(form.brand || '').trim() || null,
  model: String(form.model || '').trim() || null,
  year: form.year ? Number(form.year) : null,
  seats_min: Number(form.seats_min || 0),
  seats_max: Number(form.seats_max || 0),
  status: form.status || 'active',
  fuel_type: String(form.fuel_type || '').trim() || null,
  accessibility: !!form.accessibility,
  mileage_km: form.mileage_km ? Number(form.mileage_km) : null,
  notes: String(form.notes || '').trim() || null,
  gps_provider: String(form.gps_provider || '').trim() || null,
  gps_external_id: String(form.gps_external_id || '').trim() || null,
  documents: (form.documents || [])
    .map((doc) => ({
      id: doc.id,
      doc_type: String(doc.doc_type || '').trim(),
      reference: String(doc.reference || '').trim(),
      issue_date: String(doc.issue_date || '').trim() || null,
      expiry_date: String(doc.expiry_date || '').trim() || null,
      notes: String(doc.notes || '').trim() || null,
    }))
    .filter((doc) => doc.doc_type || doc.reference || doc.expiry_date || doc.issue_date),
});

const fromVehicle = (vehicle) => ({
  vehicle_code: vehicle?.vehicle_code || '',
  plate: vehicle?.plate || '',
  brand: vehicle?.brand || '',
  model: vehicle?.model || '',
  year: vehicle?.year || '',
  seats_min: vehicle?.seats_min || '',
  seats_max: vehicle?.seats_max || '',
  status: vehicle?.status || 'active',
  fuel_type: vehicle?.fuel_type || 'diesel',
  accessibility: !!vehicle?.accessibility,
  mileage_km: vehicle?.mileage_km || '',
  notes: vehicle?.notes || '',
  gps_provider: vehicle?.gps_provider || '',
  gps_external_id: vehicle?.gps_external_id || '',
  documents: Array.isArray(vehicle?.documents) ? vehicle.documents : [],
});

const hasGpsLink = (vehicle) => Boolean(String(vehicle?.gps_provider || '').trim() || String(vehicle?.gps_external_id || '').trim());
const hasPendingDocuments = (vehicle) => !Array.isArray(vehicle?.documents) || vehicle.documents.length === 0;
const filterChipClass = (active) => (active ? 'border-cyan-400/55 bg-cyan-500/12 text-cyan-100' : 'border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/[0.05]');

function SectionTitle({ eyebrow, title, description }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-300/90 data-mono">{eyebrow}</p>
      <h2 className="mt-1 text-[22px] font-semibold text-[#ecf4fb]" style={{ fontFamily: 'Sora, IBM Plex Sans, Segoe UI, sans-serif' }}>
        {title}
      </h2>
      <p className="mt-1 text-[12px] text-slate-400">{description}</p>
    </div>
  );
}

export default function FleetPage() {
  const [vehicles, setVehicles] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [query, setQuery] = useState('');
  const [companyFilter, setCompanyFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [assetFilter, setAssetFilter] = useState('all');
  const [selectedId, setSelectedId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [detailTab, setDetailTab] = useState('data');
  const [collapsedCompanies, setCollapsedCompanies] = useState({});
  const [form, setForm] = useState(EMPTY_FORM);
  const [importFile, setImportFile] = useState(null);
  const [importPreviewData, setImportPreviewData] = useState(null);
  const [importSummary, setImportSummary] = useState(null);
  const [primarySheetName, setPrimarySheetName] = useState('');
  const [uteName, setUteName] = useState('');
  const [previewingImport, setPreviewingImport] = useState(false);
  const [committingImport, setCommittingImport] = useState(false);
  const [weeklyPlanCache, setWeeklyPlanCache] = useState({});
  const [weeklyPlanLoading, setWeeklyPlanLoading] = useState(false);
  const [driversByCompany, setDriversByCompany] = useState({});
  const [driversLoading, setDriversLoading] = useState(false);
  const [driverForm, setDriverForm] = useState(EMPTY_DRIVER_FORM);
  const [driverEditingId, setDriverEditingId] = useState(null);
  const [driverSaving, setDriverSaving] = useState(false);
  const [driverAssignmentsDraft, setDriverAssignmentsDraft] = useState({ default_driver_id: '', days: { L: '', M: '', Mc: '', X: '', V: '' } });
  const [assignmentSaving, setAssignmentSaving] = useState(false);

  const loadFleet = async () => {
    setLoading(true);
    try {
      const data = await fetchFleetVehicles();
      const nextVehicles = data?.vehicles || [];
      setVehicles(nextVehicles);
      setSummary(data?.summary || null);
      setSelectedId((prev) => {
        if (prev && nextVehicles.some((vehicle) => String(vehicle.id) === String(prev))) return prev;
        return nextVehicles[0]?.id || null;
      });
    } catch (error) {
      notifications.error('No se pudo cargar la flota', error.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFleet();
  }, []);

  const resetImportWorkflow = () => {
    setImportPreviewData(null);
    setImportSummary(null);
    setPrimarySheetName('');
    setUteName('');
  };

  const handlePreviewImport = async () => {
    if (!importFile) {
      notifications.warning('Archivo requerido', 'Selecciona un Excel para analizar');
      return;
    }
    setPreviewingImport(true);
    try {
      const preview = await previewFleetImport(importFile);
      const sheets = Array.isArray(preview?.sheets) ? preview.sheets : [];
      const firstValidSheet = sheets.find((sheet) => sheet?.header_detected)?.sheet_name || preview?.sheet_names?.[0] || '';
      setImportPreviewData(preview || null);
      setImportSummary(null);
      setPrimarySheetName(String(firstValidSheet || ''));
      setUteName(String(firstValidSheet || '').trim() ? `UTE ${String(firstValidSheet).trim()}` : '');
      notifications.success('Archivo analizado', `${sheets.length || 0} empresas detectadas`);
    } catch (error) {
      notifications.error('No se pudo analizar el Excel', error.message);
    } finally {
      setPreviewingImport(false);
    }
  };

  const handleCommitImport = async () => {
    if (!importFile) {
      notifications.warning('Archivo requerido', 'Selecciona un Excel para importar');
      return;
    }
    if (!primarySheetName) {
      notifications.warning('Empresa principal', 'Selecciona la hoja principal antes de confirmar');
      return;
    }
    setCommittingImport(true);
    try {
      const result = await commitFleetImport({ file: importFile, primarySheetName, uteName });
      setImportSummary(result || null);
      notifications.success('Importacion completada', `${result?.total_created || 0} creados, ${result?.total_updated || 0} actualizados`);
      await loadFleet();
    } catch (error) {
      notifications.error('No se pudo confirmar la importacion', error.message);
    } finally {
      setCommittingImport(false);
    }
  };

  const filteredVehicles = useMemo(() => {
    const normalizedQuery = String(query || '').trim().toLowerCase();
    return vehicles.filter((vehicle) => {
      if (companyFilter !== 'all' && String(vehicle?.company_id || '').trim() !== companyFilter) return false;
      if (statusFilter !== 'all' && String(vehicle?.status || '').trim() !== statusFilter) return false;
      if (assetFilter === 'with_gps' && !hasGpsLink(vehicle)) return false;
      if (assetFilter === 'without_gps' && hasGpsLink(vehicle)) return false;
      if (assetFilter === 'pending_documents' && !hasPendingDocuments(vehicle)) return false;
      if (!normalizedQuery) return true;
      const haystack = [vehicle?.vehicle_code, vehicle?.plate, vehicle?.brand, vehicle?.model, vehicle?.company_name].filter(Boolean).join(' ').toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [assetFilter, companyFilter, query, statusFilter, vehicles]);

  const groupedVehicles = useMemo(() => {
    const groups = new Map();
    for (const vehicle of filteredVehicles) {
      const companyId = String(vehicle?.company_id || '').trim() || 'company_unassigned';
      const companyName = String(vehicle?.company_name || '').trim() || 'Sin empresa';
      if (!groups.has(companyId)) {
        groups.set(companyId, { companyId, companyName, vehicles: [], totalSeatsMax: 0, activeCount: 0, maintenanceCount: 0, inactiveCount: 0 });
      }
      const group = groups.get(companyId);
      group.vehicles.push(vehicle);
      group.totalSeatsMax += Number(vehicle?.seats_max || 0);
      if (vehicle?.status === 'active') group.activeCount += 1;
      if (vehicle?.status === 'maintenance') group.maintenanceCount += 1;
      if (vehicle?.status === 'inactive') group.inactiveCount += 1;
    }
    const result = Array.from(groups.values());
    result.sort((a, b) => a.companyName.localeCompare(b.companyName, 'es', { sensitivity: 'base' }));
    result.forEach((group) => {
      group.vehicles.sort((a, b) => {
        const codeDiff = String(a?.vehicle_code || '').localeCompare(String(b?.vehicle_code || ''), 'es', { sensitivity: 'base', numeric: true });
        if (codeDiff !== 0) return codeDiff;
        return String(a?.plate || '').localeCompare(String(b?.plate || ''), 'es', { sensitivity: 'base', numeric: true });
      });
    });
    return result;
  }, [filteredVehicles]);

  const companyFilterOptions = useMemo(() => {
    const map = new Map();
    vehicles.forEach((vehicle) => {
      const companyId = String(vehicle?.company_id || '').trim() || 'company_unassigned';
      const companyName = String(vehicle?.company_name || '').trim() || 'Sin empresa';
      if (!map.has(companyId)) map.set(companyId, { id: companyId, name: companyName });
    });
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name, 'es', { sensitivity: 'base' }));
  }, [vehicles]);

  useEffect(() => {
    setCollapsedCompanies((prev) => {
      const next = { ...prev };
      const selectedVehicle = vehicles.find((vehicle) => String(vehicle.id) === String(selectedId));
      const selectedCompanyId = String(selectedVehicle?.company_id || '').trim() || 'company_unassigned';
      groupedVehicles.forEach((group) => {
        if (next[group.companyId] === undefined) next[group.companyId] = true;
      });
      if (selectedVehicle && next[selectedCompanyId]) next[selectedCompanyId] = false;
      return next;
    });
  }, [groupedVehicles, selectedId, vehicles]);

  const selectedVehicle = useMemo(() => vehicles.find((vehicle) => String(vehicle.id) === String(selectedId)) || null, [selectedId, vehicles]);
  const isEditing = Boolean(editingId);
  const activeForm = isEditing ? form : (selectedVehicle ? fromVehicle(selectedVehicle) : EMPTY_FORM);
  const selectedWeeklyPlan = selectedVehicle ? weeklyPlanCache[String(selectedVehicle.id)] || null : null;
  const selectedVehicleDrivers = selectedVehicle
    ? (driversByCompany[String(selectedVehicle.company_id || '').trim()] || [])
    : [];

  const invalidateWeeklyPlan = (vehicleId) => {
    const key = String(vehicleId || '').trim();
    if (!key) return;
    setWeeklyPlanCache((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const loadVehicleWeeklyPlan = async (vehicleId, { force = false } = {}) => {
    const key = String(vehicleId || '').trim();
    if (!key) return null;
    if (!force && weeklyPlanCache[key]) return weeklyPlanCache[key];
    setWeeklyPlanLoading(true);
    try {
      const data = await fetchVehicleWeeklyPlan(key);
      setWeeklyPlanCache((prev) => ({ ...prev, [key]: data }));
      return data;
    } catch (error) {
      notifications.error('No se pudo cargar el plan semanal', error.message);
      return null;
    } finally {
      setWeeklyPlanLoading(false);
    }
  };

  useEffect(() => {
    if (!selectedVehicle || isEditing || detailTab !== 'weekly_plan') return;
    loadVehicleWeeklyPlan(selectedVehicle.id);
  }, [detailTab, isEditing, selectedVehicle]);

  const loadCompanyDrivers = async (companyId, { force = false } = {}) => {
    const key = String(companyId || '').trim();
    if (!key) return [];
    if (!force && driversByCompany[key]) return driversByCompany[key];
    setDriversLoading(true);
    try {
      const data = await fetchFleetDrivers({ companyId: key });
      setDriversByCompany((prev) => ({ ...prev, [key]: data || [] }));
      return data || [];
    } catch (error) {
      notifications.error('No se pudo cargar la lista de conductores', error.message);
      return [];
    } finally {
      setDriversLoading(false);
    }
  };

  useEffect(() => {
    if (!selectedVehicle || detailTab !== 'drivers') return;
    loadCompanyDrivers(selectedVehicle.company_id);
    setDriverAssignmentsDraft(buildDriverAssignmentDraft(selectedVehicle));
    setDriverEditingId(null);
    setDriverForm(EMPTY_DRIVER_FORM);
  }, [detailTab, selectedVehicle]);

  const handleSaveDriver = async () => {
    if (!selectedVehicle?.company_id) {
      notifications.warning('Empresa requerida', 'Selecciona primero un vehiculo con empresa');
      return;
    }
    if (!String(driverForm.full_name || '').trim()) {
      notifications.warning('Nombre requerido', 'Indica el nombre del conductor');
      return;
    }
    setDriverSaving(true);
    try {
      const payload = {
        company_id: String(selectedVehicle.company_id),
        full_name: String(driverForm.full_name || '').trim(),
        phone: String(driverForm.phone || '').trim() || null,
        email: String(driverForm.email || '').trim() || null,
        preferred_channel: driverForm.preferred_channel || 'manual',
        whatsapp_phone: String(driverForm.whatsapp_phone || '').trim() || null,
        telegram_chat_id: String(driverForm.telegram_chat_id || '').trim() || null,
        status: driverForm.status || 'active',
        notes: String(driverForm.notes || '').trim() || null,
      };
      const saved = driverEditingId
        ? await updateFleetDriver(driverEditingId, payload)
        : await createFleetDriver(payload);
      notifications.success('Conductor guardado', saved.full_name);
      await loadCompanyDrivers(selectedVehicle.company_id, { force: true });
      setDriverEditingId(null);
      setDriverForm(EMPTY_DRIVER_FORM);
    } catch (error) {
      notifications.error('No se pudo guardar el conductor', error.message);
    } finally {
      setDriverSaving(false);
    }
  };

  const handleEditDriver = (driver) => {
    setDriverEditingId(driver.id);
    setDriverForm({
      full_name: driver.full_name || '',
      phone: driver.phone || '',
      email: driver.email || '',
      preferred_channel: driver.preferred_channel || 'manual',
      whatsapp_phone: driver.whatsapp_phone || '',
      telegram_chat_id: driver.telegram_chat_id || '',
      status: driver.status || 'active',
      notes: driver.notes || '',
    });
  };

  const handleDeleteDriver = async (driver) => {
    if (!driver) return;
    if (!window.confirm(`Eliminar conductor ${driver.full_name}?`)) return;
    try {
      await deleteFleetDriver(driver.id);
      notifications.success('Conductor eliminado', driver.full_name);
      if (selectedVehicle?.company_id) {
        await loadCompanyDrivers(selectedVehicle.company_id, { force: true });
      }
      if (String(driverAssignmentsDraft.default_driver_id || '') === String(driver.id)) {
        setDriverAssignmentsDraft((prev) => ({ ...prev, default_driver_id: '' }));
      }
      setDriverAssignmentsDraft((prev) => ({
        ...prev,
        days: Object.fromEntries(Object.entries(prev.days || {}).map(([day, value]) => [day, String(value) === String(driver.id) ? '' : value])),
      }));
    } catch (error) {
      notifications.error('No se pudo eliminar el conductor', error.message);
    }
  };

  const handleSaveDriverAssignments = async () => {
    if (!selectedVehicle) return;
    setAssignmentSaving(true);
    try {
      const payload = {
        default_driver_id: String(driverAssignmentsDraft.default_driver_id || '').trim() || null,
        assignments: DRIVER_DAY_ORDER.filter((dayCode) => dayCode !== 'default').map((dayCode) => ({
          day_code: dayCode,
          driver_id: String(driverAssignmentsDraft.days?.[dayCode] || '').trim() || null,
        })),
      };
      await updateVehicleDriverAssignments(selectedVehicle.id, payload);
      notifications.success('Conductores asignados', 'La ficha del vehiculo ya refleja el reparto semanal');
      await loadFleet();
      invalidateWeeklyPlan(selectedVehicle.id);
      if (detailTab === 'weekly_plan') {
        await loadVehicleWeeklyPlan(selectedVehicle.id, { force: true });
      }
    } catch (error) {
      notifications.error('No se pudo guardar la asignacion de conductores', error.message);
    } finally {
      setAssignmentSaving(false);
    }
  };

  const startCreate = () => {
    setEditingId('new');
    setSelectedId(null);
    setDetailTab('data');
    setForm({ ...EMPTY_FORM });
  };

  const startEdit = (vehicle) => {
    setEditingId(vehicle.id);
    setSelectedId(vehicle.id);
    setDetailTab('data');
    setForm(fromVehicle(vehicle));
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm(selectedVehicle ? fromVehicle(selectedVehicle) : { ...EMPTY_FORM });
  };

  const handleSave = async () => {
    const payload = toPayload(form);
    if (!payload.vehicle_code || !payload.plate) {
      notifications.warning('Datos incompletos', 'Codigo y matricula son obligatorios');
      return;
    }
    if (!payload.seats_min || !payload.seats_max) {
      notifications.warning('Datos incompletos', 'Define el rango de plazas');
      return;
    }
    if (payload.seats_min > payload.seats_max) {
      notifications.warning('Rango invalido', 'Plazas minimas no puede ser mayor que maximas');
      return;
    }
    setSaving(true);
    try {
      if (editingId === 'new') {
        const created = await createFleetVehicle(payload);
        notifications.success('Vehiculo creado', `${created.vehicle_code} registrado`);
        setSelectedId(created.id);
        setEditingId(null);
      } else if (editingId) {
        const updated = await updateFleetVehicle(editingId, payload);
        notifications.success('Vehiculo actualizado', `${updated.vehicle_code} guardado`);
        setSelectedId(updated.id);
        setEditingId(null);
      }
      await loadFleet();
    } catch (error) {
      notifications.error('No se pudo guardar', error.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (vehicle) => {
    if (!vehicle) return;
    const ok = window.confirm(`Eliminar ${vehicle.vehicle_code} (${vehicle.plate})?`);
    if (!ok) return;
    try {
      await deleteFleetVehicle(vehicle.id);
      notifications.success('Vehiculo eliminado', vehicle.vehicle_code);
      setEditingId(null);
      await loadFleet();
    } catch (error) {
      notifications.error('No se pudo eliminar', error.message);
    }
  };

  const addDocument = () => {
    setForm((prev) => ({ ...prev, documents: [...(prev.documents || []), { doc_type: '', reference: '', issue_date: '', expiry_date: '', notes: '' }] }));
  };

  const updateDocument = (index, key, value) => {
    setForm((prev) => {
      const documents = [...(prev.documents || [])];
      documents[index] = { ...(documents[index] || {}), [key]: value };
      return { ...prev, documents };
    });
  };

  const removeDocument = (index) => {
    setForm((prev) => {
      const documents = [...(prev.documents || [])];
      documents.splice(index, 1);
      return { ...prev, documents };
    });
  };

  const downloadWeeklyPlanCsv = () => {
    if (!selectedVehicle || !selectedWeeklyPlan) return;
    const lines = [
      ['Dia', 'Hora inicio', 'Hora fin', 'Ruta', 'Workspace', 'Bus plan', 'Empresa', 'Conductor', 'Telefono', 'Tipo'],
    ];
    (selectedWeeklyPlan.days || []).forEach((day) => {
      (day.assignments || []).forEach((assignment) => {
        lines.push([
          day.day_label || DAY_LABELS[day.day] || day.day,
          assignment.start_time || minuteToLabel(assignment.start_minute),
          assignment.end_time || minuteToLabel(assignment.end_minute),
          assignment.route_id || '',
          assignment.workspace_name || assignment.workspace_id || '',
          assignment.bus_id || '',
          assignment.company_name || assignment.company_id || '',
          assignment.driver_name || '',
          assignment.driver_phone || '',
          assignment.assignment_type || '',
        ]);
      });
    });
    const csv = lines.map((row) => row.map((value) => `"${String(value ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `plan_semanal_${selectedVehicle.vehicle_code || selectedVehicle.plate || selectedVehicle.id}.csv`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="h-full min-h-0 overflow-auto rounded-[18px] control-panel p-4 md:p-5 space-y-4">
      <div className="rounded-[18px] border border-[#304a62] bg-[#0d1623]/95 p-4">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <SectionTitle
            eyebrow="Flota"
            title="Catalogo operativo de vehiculos"
            description="Organiza la flota por empresa, importa desde Excel y revisa cada vehiculo sin mezclar tareas."
          />
          <button
            type="button"
            onClick={startCreate}
            className="px-3 py-1.5 control-btn-primary rounded-md text-[11px] font-semibold uppercase tracking-[0.08em] flex items-center gap-1"
          >
            <Plus className="w-3.5 h-3.5" />
            Nuevo bus
          </button>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 xl:grid-cols-4">
          <div className="rounded-[14px] border border-[#304a62] bg-[#0b141f] p-3">
            <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Vehiculos</p>
            <p className="mt-1 text-[24px] font-semibold data-mono text-white">{summary?.total ?? 0}</p>
          </div>
          <div className="rounded-[14px] border border-[#304a62] bg-[#0b141f] p-3">
            <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Empresas</p>
            <p className="mt-1 text-[24px] font-semibold data-mono text-cyan-300">{companyFilterOptions.length}</p>
          </div>
          <div className="rounded-[14px] border border-[#304a62] bg-[#0b141f] p-3">
            <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Activos</p>
            <p className="mt-1 text-[24px] font-semibold data-mono text-emerald-300">{summary?.active ?? 0}</p>
          </div>
          <div className="rounded-[14px] border border-[#304a62] bg-[#0b141f] p-3">
            <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Plazas maximas</p>
            <p className="mt-1 text-[24px] font-semibold data-mono text-amber-200">{summary?.total_seats_max ?? 0}</p>
          </div>
        </div>
      </div>

      <div className="grid min-h-0 grid-cols-[420px_1fr] gap-4">
        <aside className="min-h-0 rounded-[18px] border border-[#304a62] bg-[#0d1623]/95 p-4 space-y-4 overflow-y-auto">
          <div className="rounded-[16px] border border-[#304a62] bg-[#0b141f] p-3 space-y-3">
            <div className="flex items-center gap-2">
              <Upload className="h-4 w-4 text-cyan-300" />
              <div>
                <p className="text-[12px] font-semibold text-white">Importar Excel de flota</p>
                <p className="text-[11px] text-slate-400">Asistente claro para empresa unica o UTE.</p>
              </div>
            </div>

            <label className="block rounded-xl border border-white/10 bg-white/[0.03] p-3">
              <span className="text-[10px] uppercase tracking-[0.08em] text-slate-500">1. Elegir archivo</span>
              <input
                type="file"
                accept=".xlsx,.xlsm,.xls"
                onChange={(event) => {
                  setImportFile(event.target.files?.[0] || null);
                  resetImportWorkflow();
                }}
                className="mt-2 w-full text-[11px] text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-cyan-500/20 file:px-3 file:py-1.5 file:text-[11px] file:font-semibold file:text-cyan-200"
              />
            </label>

            <button
              type="button"
              disabled={!importFile || previewingImport}
              onClick={handlePreviewImport}
              className="w-full rounded-md border border-cyan-500/35 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-cyan-200 hover:bg-cyan-500/10 disabled:opacity-50"
            >
              {previewingImport ? 'Analizando...' : '2. Analizar archivo'}
            </button>

            {importPreviewData && (
              <div className="rounded-xl border border-white/10 bg-[#09111b] p-3 space-y-3">
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="rounded-lg border border-white/5 bg-white/[0.03] p-2">
                    <p className="text-slate-400">Empresas detectadas</p>
                    <p className="mt-1 font-semibold text-white">{importPreviewData.sheet_names?.length || 0}</p>
                  </div>
                  <div className="rounded-lg border border-white/5 bg-white/[0.03] p-2">
                    <p className="text-slate-400">Advertencias</p>
                    <p className="mt-1 font-semibold text-amber-200">{importPreviewData.warnings?.length || 0}</p>
                  </div>
                </div>

                <label className="block">
                  <span className="text-[10px] uppercase tracking-[0.08em] text-slate-500">3. Empresa principal</span>
                  <select
                    value={primarySheetName}
                    onChange={(event) => setPrimarySheetName(event.target.value)}
                    className="mt-1 w-full rounded-md border border-white/10 bg-[#0b141f] px-3 py-2 text-[12px] text-white"
                  >
                    {(importPreviewData.sheet_names || []).map((name) => (
                      <option key={name} value={name}>{name}</option>
                    ))}
                  </select>
                </label>

                <label className="block">
                  <span className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Nombre de UTE</span>
                  <input
                    value={uteName}
                    onChange={(event) => setUteName(event.target.value)}
                    placeholder="UTE Operativa"
                    className="mt-1 w-full rounded-md border border-white/10 bg-[#0b141f] px-3 py-2 text-[12px] text-white"
                  />
                </label>

                <button
                  type="button"
                  disabled={!primarySheetName || committingImport}
                  onClick={handleCommitImport}
                  className="w-full rounded-md border border-emerald-500/35 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-emerald-200 hover:bg-emerald-500/10 disabled:opacity-50"
                >
                  {committingImport ? 'Importando...' : '4. Confirmar carga'}
                </button>

                <div className="space-y-1 max-h-[160px] overflow-auto">
                  {(importPreviewData.sheets || []).map((sheet) => (
                    <div key={sheet.sheet_name} className="rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2 text-[11px]">
                      <p className="font-semibold text-slate-100">{sheet.sheet_name}</p>
                      <p className="mt-0.5 text-slate-400">Validas {sheet.valid_rows || 0} | Invalidas {sheet.invalid_rows || 0}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {importSummary && (
              <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/[0.08] p-3 text-[11px] text-emerald-100">
                <p className="font-semibold">Importacion completada</p>
                <p className="mt-1">Principal: {importSummary.primary_company_id}</p>
                <p>UTE: {importSummary.ute_name} ({importSummary.ute_id})</p>
                <p className="mt-1">Creados {importSummary.total_created || 0} | Actualizados {importSummary.total_updated || 0} | Invalidos {importSummary.total_invalid || 0}</p>
              </div>
            )}
          </div>

          <div className="rounded-[16px] border border-[#304a62] bg-[#0b141f] p-3 space-y-3">
            <div>
              <p className="text-[12px] font-semibold text-white">Catalogo de flota</p>
              <p className="text-[11px] text-slate-400">Filtra por empresa, estado o integraciones.</p>
            </div>

            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Buscar por codigo, matricula o empresa"
              className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[12px] outline-none focus:border-cyan-500/40"
            />

            <div className="space-y-2">
              <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Empresa</p>
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => setCompanyFilter('all')} className={`rounded-full border px-3 py-1.5 text-[10px] ${filterChipClass(companyFilter === 'all')}`}>Todas</button>
                {companyFilterOptions.map((company) => (
                  <button key={company.id} type="button" onClick={() => setCompanyFilter(company.id)} className={`rounded-full border px-3 py-1.5 text-[10px] ${filterChipClass(companyFilter === company.id)}`}>
                    {company.name}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Estado</p>
              <div className="flex flex-wrap gap-2">
                {['all', 'active', 'maintenance', 'inactive'].map((status) => (
                  <button key={status} type="button" onClick={() => setStatusFilter(status)} className={`rounded-full border px-3 py-1.5 text-[10px] ${filterChipClass(statusFilter === status)}`}>
                    {status === 'all' ? 'Todos' : STATUS_LABEL[status]}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Atajos</p>
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => setAssetFilter('all')} className={`rounded-full border px-3 py-1.5 text-[10px] ${filterChipClass(assetFilter === 'all')}`}>Todos</button>
                <button type="button" onClick={() => setAssetFilter('with_gps')} className={`rounded-full border px-3 py-1.5 text-[10px] ${filterChipClass(assetFilter === 'with_gps')}`}>Con GPS</button>
                <button type="button" onClick={() => setAssetFilter('without_gps')} className={`rounded-full border px-3 py-1.5 text-[10px] ${filterChipClass(assetFilter === 'without_gps')}`}>Sin GPS</button>
                <button type="button" onClick={() => setAssetFilter('pending_documents')} className={`rounded-full border px-3 py-1.5 text-[10px] ${filterChipClass(assetFilter === 'pending_documents')}`}>Documentos pendientes</button>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            {loading && <p className="text-[12px] text-slate-500">Cargando flota...</p>}
            {!loading && groupedVehicles.length === 0 && (
              <div className="rounded-[16px] border border-[#304a62] bg-[#0b141f] p-6 text-center">
                <Bus className="mx-auto h-6 w-6 text-slate-500" />
                <p className="mt-2 text-[12px] text-slate-300">No hay vehiculos para el filtro actual.</p>
              </div>
            )}

            {groupedVehicles.map((group) => {
              const isCollapsed = collapsedCompanies[group.companyId] !== false;
              return (
                <div key={group.companyId} className="rounded-[16px] border border-[#304a62] bg-[#0b141f] overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setCollapsedCompanies((prev) => ({ ...prev, [group.companyId]: !isCollapsed }))}
                    className="w-full px-3 py-3 text-left bg-white/[0.03] hover:bg-white/[0.05] transition"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0 flex items-center gap-2">
                        <Building2 className="h-4 w-4 text-cyan-300 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-[12px] font-semibold text-white truncate">{group.companyName}</p>
                          <p className="text-[10px] text-slate-400">{group.vehicles.length} buses | {group.totalSeatsMax} plazas maximas</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 text-[9px] data-mono">
                        <span className="rounded bg-emerald-500/[0.16] px-1.5 py-0.5 text-emerald-200">{group.activeCount} A</span>
                        <span className="rounded bg-amber-500/[0.16] px-1.5 py-0.5 text-amber-200">{group.maintenanceCount} T</span>
                        <span className="rounded bg-slate-500/[0.16] px-1.5 py-0.5 text-slate-200">{group.inactiveCount} I</span>
                      </div>
                    </div>
                  </button>

                  {!isCollapsed && (
                    <div className="p-3 space-y-2">
                      {group.vehicles.map((vehicle) => {
                        const selected = String(vehicle.id) === String(selectedId);
                        return (
                          <button
                            key={vehicle.id}
                            type="button"
                            onClick={() => {
                              setSelectedId(vehicle.id);
                              setDetailTab('data');
                              if (!isEditing) setForm(fromVehicle(vehicle));
                            }}
                            className={`w-full rounded-[14px] border p-3 text-left transition ${
                              selected ? 'border-cyan-400/60 bg-cyan-500/[0.12]' : 'border-white/10 bg-white/[0.03] hover:bg-white/[0.05]'
                            }`}
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-[13px] font-semibold text-white data-mono">{vehicle.vehicle_code}</p>
                                <p className="mt-1 text-[11px] text-slate-300 data-mono">{vehicle.plate}</p>
                              </div>
                              <span className={`rounded-md px-2 py-1 text-[10px] font-semibold ${
                                vehicle.status === 'active'
                                  ? 'bg-emerald-500/[0.16] text-emerald-200'
                                  : vehicle.status === 'maintenance'
                                    ? 'bg-amber-500/[0.16] text-amber-200'
                                    : 'bg-slate-500/[0.18] text-slate-200'
                              }`}>
                                {STATUS_LABEL[vehicle.status] || vehicle.status}
                              </span>
                            </div>
                            <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px] text-slate-400">
                              <span className="rounded-md border border-white/5 bg-white/[0.03] px-2 py-1">{vehicle.seats_min}-{vehicle.seats_max} plazas</span>
                              {hasGpsLink(vehicle) && <span className="rounded-md border border-cyan-500/20 bg-cyan-500/10 px-2 py-1 text-cyan-100">GPS</span>}
                              {hasPendingDocuments(vehicle) && <span className="rounded-md border border-amber-500/20 bg-amber-500/10 px-2 py-1 text-amber-100">Doc pendiente</span>}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </aside>

        <section className="min-h-0 rounded-[18px] border border-[#304a62] bg-[#0d1623]/95 p-4 overflow-y-auto">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.14em] text-cyan-300/90 data-mono">Detalle</p>
              <h3 className="mt-1 text-[20px] font-semibold text-white">
                {isEditing ? (editingId === 'new' ? 'Nuevo vehiculo' : 'Edicion de vehiculo') : (selectedVehicle?.vehicle_code || 'Selecciona un vehiculo')}
              </h3>
              <p className="mt-1 text-[12px] text-slate-400">
                {isEditing
                  ? 'Completa datos, documentos y vinculacion GPS sin salir de la ficha.'
                  : 'Consulta informacion operativa, documentacion y telematica de cada unidad.'}
              </p>
            </div>

            <div className="flex items-center gap-2">
              {selectedVehicle && !isEditing && detailTab === 'weekly_plan' && (
                <button onClick={downloadWeeklyPlanCsv} className="control-btn px-3 py-1.5 rounded-md text-[11px] flex items-center gap-1.5">
                  <Download size={12} />
                  Descargar CSV
                </button>
              )}
              {selectedVehicle && !isEditing && (
                <>
                  <button onClick={() => startEdit(selectedVehicle)} className="control-btn px-3 py-1.5 rounded-md text-[11px] flex items-center gap-1.5">
                    <Pencil size={12} />
                    Editar
                  </button>
                  <button onClick={() => handleDelete(selectedVehicle)} className="px-3 py-1.5 rounded-md text-[11px] border border-red-500/35 text-red-300 hover:bg-red-500/[0.08] flex items-center gap-1.5">
                    <Trash2 size={12} />
                    Eliminar
                  </button>
                </>
              )}
              {isEditing && (
                <>
                  <button onClick={cancelEdit} className="px-3 py-1.5 rounded-md text-[11px] border border-white/[0.2] text-slate-300 hover:bg-white/[0.06] flex items-center gap-1.5">
                    <X size={12} />
                    Cancelar
                  </button>
                  <button onClick={handleSave} disabled={saving} className="control-btn-primary px-3 py-1.5 rounded-md text-[11px] flex items-center gap-1.5 disabled:opacity-50">
                    <Save size={12} />
                    {saving ? 'Guardando...' : 'Guardar'}
                  </button>
                </>
              )}
            </div>
          </div>

          {!selectedVehicle && !isEditing ? (
            <div className="mt-6 flex h-[60vh] items-center justify-center rounded-[16px] border border-dashed border-white/[0.12]">
              <div className="max-w-sm text-center">
                <Bus className="mx-auto h-7 w-7 text-slate-500" />
                <p className="mt-3 text-[14px] font-medium text-slate-200">Todavia no hay un vehiculo seleccionado</p>
                <p className="mt-1 text-[12px] text-slate-400">Elige un bus del catalogo o crea uno nuevo para revisar datos, documentos y GPS.</p>
                <div className="mt-4 flex items-center justify-center gap-2">
                  <button type="button" onClick={startCreate} className="control-btn-primary rounded-md px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em]">
                    Nuevo bus
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="mt-5 space-y-4">
              {!isEditing && selectedVehicle && (
                <div className="grid grid-cols-2 gap-3 xl:grid-cols-5">
                  <div className="rounded-[14px] border border-white/5 bg-white/[0.03] p-3">
                    <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Empresa</p>
                    <p className="mt-1 text-[13px] font-semibold text-white">{selectedVehicle.company_name || selectedVehicle.company_id || 'Sin empresa'}</p>
                  </div>
                  <div className="rounded-[14px] border border-white/5 bg-white/[0.03] p-3">
                    <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Estado</p>
                    <p className="mt-1 text-[13px] font-semibold text-white">{STATUS_LABEL[selectedVehicle.status] || selectedVehicle.status}</p>
                  </div>
                  <div className="rounded-[14px] border border-white/5 bg-white/[0.03] p-3">
                    <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Plazas</p>
                    <p className="mt-1 text-[13px] font-semibold text-white data-mono">{selectedVehicle.seats_min}-{selectedVehicle.seats_max}</p>
                  </div>
                  <div className="rounded-[14px] border border-white/5 bg-white/[0.03] p-3">
                    <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">GPS</p>
                    <p className="mt-1 text-[13px] font-semibold text-white">{hasGpsLink(selectedVehicle) ? 'Vinculado' : 'Pendiente'}</p>
                  </div>
                  <div className="rounded-[14px] border border-white/5 bg-white/[0.03] p-3">
                    <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Conductor habitual</p>
                    <p className="mt-1 text-[13px] font-semibold text-white">{selectedVehicle.default_driver_name || 'Sin asignar'}</p>
                  </div>
                </div>
              )}

              <div className="flex items-center gap-2">
                {DETAIL_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setDetailTab(tab.id)}
                    className={`rounded-full border px-3 py-1.5 text-[11px] font-semibold transition ${
                      detailTab === tab.id ? 'border-cyan-400/55 bg-cyan-500/12 text-cyan-100' : 'border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/[0.05]'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {detailTab === 'data' && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <label className="space-y-1">
                      <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Codigo</span>
                      <input value={activeForm.vehicle_code} disabled={!isEditing} onChange={(event) => setForm((prev) => ({ ...prev, vehicle_code: event.target.value }))} className="w-full rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px] disabled:opacity-70" />
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Matricula</span>
                      <input value={activeForm.plate} disabled={!isEditing} onChange={(event) => setForm((prev) => ({ ...prev, plate: event.target.value }))} className="w-full rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px] disabled:opacity-70 data-mono" />
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Marca</span>
                      <input value={activeForm.brand} disabled={!isEditing} onChange={(event) => setForm((prev) => ({ ...prev, brand: event.target.value }))} className="w-full rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px] disabled:opacity-70" />
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Modelo</span>
                      <input value={activeForm.model} disabled={!isEditing} onChange={(event) => setForm((prev) => ({ ...prev, model: event.target.value }))} className="w-full rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px] disabled:opacity-70" />
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Ano</span>
                      <input type="number" value={activeForm.year} disabled={!isEditing} onChange={(event) => setForm((prev) => ({ ...prev, year: event.target.value }))} className="w-full rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px] disabled:opacity-70" />
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Estado</span>
                      <select value={activeForm.status} disabled={!isEditing} onChange={(event) => setForm((prev) => ({ ...prev, status: event.target.value }))} className="w-full rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px] disabled:opacity-70">
                        <option value="active">Activo</option>
                        <option value="maintenance">Taller</option>
                        <option value="inactive">Inactivo</option>
                      </select>
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Plazas minimas</span>
                      <input type="number" value={activeForm.seats_min} disabled={!isEditing} onChange={(event) => setForm((prev) => ({ ...prev, seats_min: event.target.value }))} className="w-full rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px] disabled:opacity-70" />
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Plazas maximas</span>
                      <input type="number" value={activeForm.seats_max} disabled={!isEditing} onChange={(event) => setForm((prev) => ({ ...prev, seats_max: event.target.value }))} className="w-full rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px] disabled:opacity-70" />
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Combustible</span>
                      <input value={activeForm.fuel_type} disabled={!isEditing} onChange={(event) => setForm((prev) => ({ ...prev, fuel_type: event.target.value }))} className="w-full rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px] disabled:opacity-70" />
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Kilometraje</span>
                      <input type="number" value={activeForm.mileage_km} disabled={!isEditing} onChange={(event) => setForm((prev) => ({ ...prev, mileage_km: event.target.value }))} className="w-full rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px] disabled:opacity-70" />
                    </label>
                  </div>

                  <label className="flex items-center gap-2 text-[12px] text-slate-300">
                    <input type="checkbox" checked={!!activeForm.accessibility} disabled={!isEditing} onChange={(event) => setForm((prev) => ({ ...prev, accessibility: event.target.checked }))} />
                    Accesible PMR
                  </label>

                  <label className="block space-y-1">
                    <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Notas operativas</span>
                    <textarea value={activeForm.notes || ''} disabled={!isEditing} onChange={(event) => setForm((prev) => ({ ...prev, notes: event.target.value }))} rows={4} className="w-full rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px] disabled:opacity-70" />
                  </label>

                  {!isEditing && selectedVehicle && (
                    <div className="text-[11px] text-slate-500 data-mono">
                      <span className="mr-3">Edad: {selectedVehicle.age_years ?? '-'} anos</span>
                      <span>Actualizado: {selectedVehicle.updated_at?.slice(0, 19).replace('T', ' ') || '-'}</span>
                    </div>
                  )}
                </div>
              )}

              {detailTab === 'drivers' && selectedVehicle && (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 gap-3 xl:grid-cols-4">
                    <div className="rounded-[14px] border border-white/10 bg-white/[0.03] p-3 xl:col-span-2">
                      <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Conductor habitual</p>
                      <p className="mt-1 text-[16px] font-semibold text-white">{selectedVehicle.default_driver_name || 'Sin asignar'}</p>
                      <p className="mt-1 text-[11px] text-slate-400">{selectedVehicle.default_driver_phone || 'Sin telefono registrado'}</p>
                    </div>
                    <div className="rounded-[14px] border border-white/10 bg-white/[0.03] p-3">
                      <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Conductores de empresa</p>
                      <p className="mt-1 text-[20px] font-semibold data-mono text-cyan-300">{selectedVehicleDrivers.length}</p>
                    </div>
                    <div className="rounded-[14px] border border-white/10 bg-white/[0.03] p-3">
                      <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Dias configurados</p>
                      <p className="mt-1 text-[20px] font-semibold data-mono text-amber-200">
                        {Object.values(driverAssignmentsDraft.days || {}).filter(Boolean).length}
                      </p>
                    </div>
                  </div>

                  <div className="rounded-[16px] border border-white/10 bg-white/[0.03] p-4 space-y-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-cyan-300" />
                        <div>
                          <p className="text-[12px] font-semibold text-white">Asignacion semanal de conductores</p>
                          <p className="text-[11px] text-slate-400">Define quien usa este autobus habitualmente y quien lo lleva cada dia si rota.</p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={handleSaveDriverAssignments}
                        disabled={assignmentSaving || driversLoading}
                        className="control-btn-primary rounded-md px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] disabled:opacity-60"
                      >
                        {assignmentSaving ? 'Guardando...' : 'Guardar asignacion'}
                      </button>
                    </div>

                    <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                      <label className="space-y-1">
                        <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Conductor habitual</span>
                        <select
                          value={driverAssignmentsDraft.default_driver_id}
                          onChange={(event) => setDriverAssignmentsDraft((prev) => ({ ...prev, default_driver_id: event.target.value }))}
                          className="w-full rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px]"
                        >
                          <option value="">Sin asignar</option>
                          {selectedVehicleDrivers.map((driver) => (
                            <option key={driver.id} value={driver.id}>
                              {driver.full_name} {driver.phone ? `· ${driver.phone}` : ''}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="rounded-[14px] border border-white/5 bg-[#0f1723] p-3 text-[11px] text-slate-400">
                        Si un dia no tiene conductor propio, el sistema usara el habitual como referencia operativa y futura base de envio.
                      </div>
                    </div>

                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
                      {Object.entries(DAY_LABELS).map(([dayCode, dayLabel]) => (
                        <label key={dayCode} className="space-y-1 rounded-[14px] border border-white/5 bg-[#0f1723] p-3">
                          <span className="text-[10px] uppercase tracking-[0.08em] text-slate-500">{dayLabel}</span>
                          <select
                            value={driverAssignmentsDraft.days?.[dayCode] || ''}
                            onChange={(event) => setDriverAssignmentsDraft((prev) => ({
                              ...prev,
                              days: { ...(prev.days || {}), [dayCode]: event.target.value },
                            }))}
                            className="w-full rounded-md border border-white/10 bg-[#09111b] px-3 py-2 text-[12px]"
                          >
                            <option value="">Usar habitual</option>
                            {selectedVehicleDrivers.map((driver) => (
                              <option key={driver.id} value={driver.id}>
                                {driver.full_name}
                              </option>
                            ))}
                          </select>
                        </label>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-4 xl:grid-cols-[420px_1fr]">
                    <div className="rounded-[16px] border border-white/10 bg-white/[0.03] p-4 space-y-3">
                      <div className="flex items-center gap-2">
                        <Phone className="h-4 w-4 text-cyan-300" />
                        <div>
                          <p className="text-[12px] font-semibold text-white">{driverEditingId ? 'Editar conductor' : 'Nuevo conductor'}</p>
                          <p className="text-[11px] text-slate-400">Prepara ya la ficha para futuras comunicaciones automaticas.</p>
                        </div>
                      </div>
                      <div className="grid grid-cols-1 gap-3">
                        <input value={driverForm.full_name} onChange={(event) => setDriverForm((prev) => ({ ...prev, full_name: event.target.value }))} placeholder="Nombre completo" className="rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px]" />
                        <input value={driverForm.phone} onChange={(event) => setDriverForm((prev) => ({ ...prev, phone: event.target.value }))} placeholder="Telefono" className="rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px]" />
                        <input value={driverForm.email} onChange={(event) => setDriverForm((prev) => ({ ...prev, email: event.target.value }))} placeholder="Email (opcional)" className="rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px]" />
                        <div className="grid grid-cols-2 gap-3">
                          <select value={driverForm.preferred_channel} onChange={(event) => setDriverForm((prev) => ({ ...prev, preferred_channel: event.target.value }))} className="rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px]">
                            {Object.entries(DRIVER_CHANNEL_LABELS).map(([value, label]) => (
                              <option key={value} value={value}>{label}</option>
                            ))}
                          </select>
                          <select value={driverForm.status} onChange={(event) => setDriverForm((prev) => ({ ...prev, status: event.target.value }))} className="rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px]">
                            <option value="active">Activo</option>
                            <option value="inactive">Inactivo</option>
                          </select>
                        </div>
                        <input value={driverForm.whatsapp_phone} onChange={(event) => setDriverForm((prev) => ({ ...prev, whatsapp_phone: event.target.value }))} placeholder="WhatsApp (opcional)" className="rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px]" />
                        <input value={driverForm.telegram_chat_id} onChange={(event) => setDriverForm((prev) => ({ ...prev, telegram_chat_id: event.target.value }))} placeholder="Telegram chat id (opcional)" className="rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px]" />
                        <textarea value={driverForm.notes} onChange={(event) => setDriverForm((prev) => ({ ...prev, notes: event.target.value }))} rows={3} placeholder="Notas" className="rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px]" />
                      </div>
                      <div className="flex items-center gap-2">
                        <button type="button" onClick={handleSaveDriver} disabled={driverSaving} className="control-btn-primary rounded-md px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] disabled:opacity-60">
                          {driverSaving ? 'Guardando...' : (driverEditingId ? 'Guardar conductor' : 'Crear conductor')}
                        </button>
                        {driverEditingId && (
                          <button type="button" onClick={() => { setDriverEditingId(null); setDriverForm(EMPTY_DRIVER_FORM); }} className="control-btn rounded-md px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em]">
                            Cancelar
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="rounded-[16px] border border-white/10 bg-white/[0.03] p-4 space-y-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-[12px] font-semibold text-white">Conductores disponibles</p>
                          <p className="text-[11px] text-slate-400">Solo se muestran los conductores de la empresa propietaria del autobus.</p>
                        </div>
                        <button type="button" onClick={() => loadCompanyDrivers(selectedVehicle.company_id, { force: true })} className="control-btn rounded-md px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em]">
                          {driversLoading ? 'Cargando...' : 'Actualizar'}
                        </button>
                      </div>

                      {selectedVehicleDrivers.length === 0 ? (
                        <div className="rounded-xl border border-dashed border-white/10 p-4 text-[12px] text-slate-400">
                          Todavia no hay conductores cargados para esta empresa.
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {selectedVehicleDrivers.map((driver) => (
                            <div key={driver.id} className="flex items-start justify-between gap-3 rounded-[14px] border border-white/10 bg-[#0f1723] p-3">
                              <div className="min-w-0">
                                <p className="truncate text-[13px] font-semibold text-white">{driver.full_name}</p>
                                <p className="truncate text-[11px] text-slate-400">{driver.phone || 'Sin telefono'} · {DRIVER_CHANNEL_LABELS[driver.preferred_channel] || driver.preferred_channel}</p>
                                <p className="truncate text-[10px] text-slate-500">{driver.status === 'active' ? 'Activo' : 'Inactivo'}</p>
                              </div>
                              <div className="flex items-center gap-2">
                                <button type="button" onClick={() => setDriverAssignmentsDraft((prev) => ({ ...prev, default_driver_id: driver.id }))} className="control-btn rounded-md px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em]">
                                  Habitual
                                </button>
                                <button type="button" onClick={() => handleEditDriver(driver)} className="control-btn rounded-md px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em]">
                                  Editar
                                </button>
                                <button type="button" onClick={() => handleDeleteDriver(driver)} className="rounded-md border border-red-500/35 px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-red-300 hover:bg-red-500/10">
                                  Borrar
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {detailTab === 'documents' && (
                <div className="rounded-[16px] border border-white/10 bg-white/[0.03] p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-cyan-300" />
                      <div>
                        <p className="text-[12px] font-semibold text-white">Documentacion</p>
                        <p className="text-[11px] text-slate-400">ITV, seguros y referencias basicas del vehiculo.</p>
                      </div>
                    </div>
                    {isEditing && (
                      <button onClick={addDocument} className="control-btn rounded-md px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em]">
                        Anadir documento
                      </button>
                    )}
                  </div>

                  {(activeForm.documents || []).length === 0 ? (
                    <div className="rounded-xl border border-dashed border-white/10 p-4 text-center">
                      <p className="text-[12px] text-slate-300">Todavia no hay documentos cargados.</p>
                      <p className="mt-1 text-[11px] text-slate-500">Puedes completarlos manualmente cuando lo necesites.</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {(activeForm.documents || []).map((doc, index) => (
                        <div key={`${doc.id || 'doc'}-${index}`} className="grid grid-cols-[1fr_1fr_140px_140px_40px] gap-2 rounded-xl border border-white/10 bg-[#0f1723] p-2">
                          <input value={doc.doc_type || ''} disabled={!isEditing} onChange={(event) => updateDocument(index, 'doc_type', event.target.value)} placeholder="Tipo" className="rounded-md border border-white/10 bg-[#09111b] px-2 py-1.5 text-[11px]" />
                          <input value={doc.reference || ''} disabled={!isEditing} onChange={(event) => updateDocument(index, 'reference', event.target.value)} placeholder="Referencia" className="rounded-md border border-white/10 bg-[#09111b] px-2 py-1.5 text-[11px]" />
                          <input type="date" value={doc.issue_date || ''} disabled={!isEditing} onChange={(event) => updateDocument(index, 'issue_date', event.target.value)} className="rounded-md border border-white/10 bg-[#09111b] px-2 py-1.5 text-[11px]" />
                          <input type="date" value={doc.expiry_date || ''} disabled={!isEditing} onChange={(event) => updateDocument(index, 'expiry_date', event.target.value)} className="rounded-md border border-white/10 bg-[#09111b] px-2 py-1.5 text-[11px]" />
                          <button disabled={!isEditing} onClick={() => removeDocument(index)} className="rounded-md border border-red-500/35 text-red-300 hover:bg-red-500/10 disabled:opacity-40">
                            <Trash2 size={12} className="mx-auto" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {detailTab === 'gps' && (
                <div className="rounded-[16px] border border-white/10 bg-white/[0.03] p-4 space-y-4">
                  <div className="flex items-center gap-2">
                    <MapPin className="h-4 w-4 text-cyan-300" />
                    <div>
                      <p className="text-[12px] font-semibold text-white">Vinculacion GPS</p>
                      <p className="text-[11px] text-slate-400">Base preparada para integrar el proveedor externo de telematica.</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <label className="space-y-1">
                      <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Proveedor</span>
                      <input value={activeForm.gps_provider || ''} disabled={!isEditing} onChange={(event) => setForm((prev) => ({ ...prev, gps_provider: event.target.value }))} className="w-full rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px] disabled:opacity-70" />
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">ID externo</span>
                      <input value={activeForm.gps_external_id || ''} disabled={!isEditing} onChange={(event) => setForm((prev) => ({ ...prev, gps_external_id: event.target.value }))} className="w-full rounded-md border border-white/10 bg-[#0f1723] px-3 py-2 text-[12px] disabled:opacity-70 data-mono" />
                    </label>
                  </div>

                  {!isEditing && selectedVehicle && (
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      <div className="rounded-xl border border-white/5 bg-[#0f1723] p-3">
                        <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Ultima lectura</p>
                        <p className="mt-1 text-[12px] text-slate-200">{selectedVehicle.gps_last_seen_at || 'Sin datos'}</p>
                      </div>
                      <div className="rounded-xl border border-white/5 bg-[#0f1723] p-3">
                        <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Ultima posicion</p>
                        <p className="mt-1 text-[12px] text-slate-200">
                          {selectedVehicle.gps_last_position ? `${selectedVehicle.gps_last_position.lat}, ${selectedVehicle.gps_last_position.lon}` : 'Sin posicion registrada'}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {detailTab === 'weekly_plan' && (
                <div className="rounded-[16px] border border-white/10 bg-white/[0.03] p-4 space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[12px] font-semibold text-white">Plan semanal publicado</p>
                      <p className="text-[11px] text-slate-400">Muestra la agenda operativa real del vehiculo segun las optimizaciones ya publicadas.</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => selectedVehicle && loadVehicleWeeklyPlan(selectedVehicle.id, { force: true })}
                      className="control-btn rounded-md px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em]"
                    >
                      {weeklyPlanLoading ? 'Actualizando...' : 'Actualizar'}
                    </button>
                  </div>

                  {!selectedVehicle ? null : weeklyPlanLoading && !selectedWeeklyPlan ? (
                    <div className="rounded-xl border border-white/10 bg-[#0f1723] p-4 text-[12px] text-slate-300">
                      Cargando plan semanal...
                    </div>
                  ) : (
                    <>
                      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
                        <div className="rounded-[14px] border border-white/5 bg-[#0f1723] p-3">
                          <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Servicios</p>
                          <p className="mt-1 text-[20px] font-semibold data-mono text-white">{selectedWeeklyPlan?.total_assignments ?? 0}</p>
                        </div>
                        <div className="rounded-[14px] border border-white/5 bg-[#0f1723] p-3">
                          <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Dias con servicio</p>
                          <p className="mt-1 text-[20px] font-semibold data-mono text-cyan-300">{selectedWeeklyPlan?.total_days_with_service ?? 0}</p>
                        </div>
                        <div className="rounded-[14px] border border-white/5 bg-[#0f1723] p-3">
                          <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Workspaces</p>
                          <p className="mt-1 text-[20px] font-semibold data-mono text-amber-200">{selectedWeeklyPlan?.total_workspaces ?? 0}</p>
                        </div>
                        <div className="rounded-[14px] border border-white/5 bg-[#0f1723] p-3">
                          <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Vehiculo</p>
                          <p className="mt-1 text-[13px] font-semibold text-white data-mono">{selectedVehicle.plate || selectedVehicle.vehicle_code}</p>
                        </div>
                      </div>

                      <div className="rounded-[14px] border border-white/5 bg-[#0f1723] p-3">
                        <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Conductor habitual</p>
                        <p className="mt-1 text-[13px] font-semibold text-white">{selectedWeeklyPlan?.default_driver_name || selectedVehicle.default_driver_name || 'Sin asignar'}</p>
                        <p className="mt-1 text-[11px] text-slate-400">
                          {selectedWeeklyPlan?.default_driver_phone || selectedVehicle.default_driver_phone || 'Sin telefono'}
                          {' · '}
                          {DRIVER_CHANNEL_LABELS[selectedWeeklyPlan?.default_driver_channel || selectedVehicle.default_driver_channel] || 'Manual'}
                        </p>
                      </div>

                      <div className="space-y-3">
                        {(selectedWeeklyPlan?.days || []).map((day) => (
                          <div key={day.day} className="rounded-[14px] border border-white/10 bg-[#0f1723] overflow-hidden">
                            <div className="flex items-center justify-between gap-3 border-b border-white/5 bg-white/[0.03] px-3 py-2">
                              <div>
                                <p className="text-[12px] font-semibold text-white">{day.day_label || DAY_LABELS[day.day] || day.day}</p>
                                <p className="text-[10px] text-slate-400">
                                  {day.route_count || 0} servicios
                                  {day.first_start_minute != null && day.last_end_minute != null
                                    ? ` · ${minuteToLabel(day.first_start_minute)} - ${minuteToLabel(day.last_end_minute)}`
                                    : ''}
                                </p>
                              </div>
                              <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[10px] text-slate-300 data-mono">
                                {day.route_count || 0}
                              </span>
                            </div>

                            {(day.assignments || []).length === 0 ? (
                              <div className="px-3 py-3 text-[11px] text-slate-500">Sin servicio publicado para este dia.</div>
                            ) : (
                              <div className="divide-y divide-white/5">
                                {(day.assignments || []).map((assignment, index) => (
                                  <div key={`${day.day}-${assignment.route_id}-${index}`} className="grid grid-cols-[110px_1fr_180px_180px_110px] gap-3 px-3 py-2 text-[11px]">
                                    <div className="text-slate-200 data-mono">
                                      {assignment.start_time || minuteToLabel(assignment.start_minute)} - {assignment.end_time || minuteToLabel(assignment.end_minute)}
                                    </div>
                                    <div className="min-w-0">
                                      <p className="truncate font-semibold text-white data-mono">{assignment.route_id}</p>
                                      <p className="truncate text-slate-400">{assignment.workspace_name || assignment.workspace_id}</p>
                                    </div>
                                    <div className="min-w-0 text-slate-300">
                                      <p className="truncate">Plan {assignment.bus_id}</p>
                                      <p className="truncate text-slate-500">{assignment.company_name || assignment.company_id || 'Sin empresa'}</p>
                                    </div>
                                    <div className="min-w-0 text-slate-300">
                                      <p className="truncate">{assignment.driver_name || selectedWeeklyPlan?.default_driver_name || 'Sin conductor'}</p>
                                      <p className="truncate text-slate-500">
                                        {assignment.driver_phone || selectedWeeklyPlan?.default_driver_phone || 'Sin telefono'}
                                        {assignment.preferred_channel ? ` · ${DRIVER_CHANNEL_LABELS[assignment.preferred_channel] || assignment.preferred_channel}` : ''}
                                      </p>
                                    </div>
                                    <div className="text-right">
                                      <span className={`rounded-md px-2 py-1 text-[10px] font-semibold ${assignment.assignment_type === 'real' ? 'bg-emerald-500/[0.16] text-emerald-200' : 'bg-amber-500/[0.16] text-amber-200'}`}>
                                        {assignment.assignment_type === 'real' ? 'REAL' : 'PROVISIONAL'}
                                      </span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
