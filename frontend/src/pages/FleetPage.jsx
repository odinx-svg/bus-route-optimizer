import React, { useEffect, useMemo, useState } from 'react';
import { Plus, Pencil, Trash2, Save, X, FileText, Bus } from 'lucide-react';
import { notifications } from '../services/notifications';
import {
  fetchFleetVehicles,
  createFleetVehicle,
  updateFleetVehicle,
  deleteFleetVehicle,
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
  documents: [],
};

const STATUS_LABEL = {
  active: 'Activo',
  maintenance: 'Taller',
  inactive: 'Inactivo',
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
  documents: Array.isArray(vehicle?.documents) ? vehicle.documents : [],
});

export default function FleetPage() {
  const [vehicles, setVehicles] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);

  const loadFleet = async () => {
    setLoading(true);
    try {
      const data = await fetchFleetVehicles();
      setVehicles(data?.vehicles || []);
      setSummary(data?.summary || null);
      if (!selectedId && data?.vehicles?.length) {
        setSelectedId(data.vehicles[0].id);
      }
    } catch (error) {
      notifications.error('No se pudo cargar la flota', error.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFleet();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredVehicles = useMemo(() => {
    const sorted = [...vehicles];
    if (!query.trim()) return sorted;
    const q = query.toLowerCase();
    return sorted.filter((v) => (
      String(v.vehicle_code || '').toLowerCase().includes(q) ||
      String(v.plate || '').toLowerCase().includes(q) ||
      String(v.brand || '').toLowerCase().includes(q) ||
      String(v.model || '').toLowerCase().includes(q)
    ));
  }, [vehicles, query]);

  const selectedVehicle = useMemo(
    () => vehicles.find((v) => String(v.id) === String(selectedId)) || null,
    [vehicles, selectedId]
  );

  const startCreate = () => {
    setEditingId('new');
    setSelectedId(null);
    setForm({ ...EMPTY_FORM });
  };

  const startEdit = (vehicle) => {
    setEditingId(vehicle.id);
    setSelectedId(vehicle.id);
    setForm(fromVehicle(vehicle));
  };

  const cancelEdit = () => {
    setEditingId(null);
    if (selectedVehicle) {
      setForm(fromVehicle(selectedVehicle));
    } else {
      setForm({ ...EMPTY_FORM });
    }
  };

  const handleSave = async () => {
    const payload = toPayload(form);
    if (!payload.vehicle_code || !payload.plate) {
      notifications.warning('Datos incompletos', 'Código y matrícula son obligatorios');
      return;
    }
    if (!payload.seats_min || !payload.seats_max) {
      notifications.warning('Datos incompletos', 'Define el rango de plazas');
      return;
    }
    if (payload.seats_min > payload.seats_max) {
      notifications.warning('Rango inválido', 'Plazas mínimas no puede ser mayor que máximas');
      return;
    }

    setSaving(true);
    try {
      if (editingId === 'new') {
        const created = await createFleetVehicle(payload);
        setVehicles((prev) => [...prev, created]);
        setSelectedId(created.id);
        setEditingId(null);
        notifications.success('Vehículo creado', `${created.vehicle_code} registrado`);
      } else if (editingId) {
        const updated = await updateFleetVehicle(editingId, payload);
        setVehicles((prev) => prev.map((v) => (v.id === editingId ? updated : v)));
        setSelectedId(updated.id);
        setEditingId(null);
        notifications.success('Vehículo actualizado', `${updated.vehicle_code} guardado`);
      }
      const refreshed = await fetchFleetVehicles();
      setVehicles(refreshed?.vehicles || []);
      setSummary(refreshed?.summary || null);
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
      notifications.success('Vehículo eliminado', vehicle.vehicle_code);
      const next = vehicles.filter((v) => v.id !== vehicle.id);
      setVehicles(next);
      setSummary((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          total: Math.max(0, Number(prev.total || 1) - 1),
        };
      });
      if (selectedId === vehicle.id) {
        setSelectedId(next[0]?.id || null);
      }
      setEditingId(null);
      await loadFleet();
    } catch (error) {
      notifications.error('No se pudo eliminar', error.message);
    }
  };

  const addDocument = () => {
    setForm((prev) => ({
      ...prev,
      documents: [...(prev.documents || []), { doc_type: '', reference: '', issue_date: '', expiry_date: '', notes: '' }],
    }));
  };

  const updateDocument = (idx, key, value) => {
    setForm((prev) => {
      const docs = [...(prev.documents || [])];
      docs[idx] = { ...(docs[idx] || {}), [key]: value };
      return { ...prev, documents: docs };
    });
  };

  const removeDocument = (idx) => {
    setForm((prev) => {
      const docs = [...(prev.documents || [])];
      docs.splice(idx, 1);
      return { ...prev, documents: docs };
    });
  };

  const isEditing = !!editingId;
  const activeForm = isEditing ? form : (selectedVehicle ? fromVehicle(selectedVehicle) : EMPTY_FORM);

  return (
    <div className="h-full min-h-0 grid grid-cols-[360px_1fr] gap-3">
      <aside className="control-panel rounded-[16px] overflow-hidden flex flex-col min-h-0">
        <div className="p-4 border-b border-[#2b4056] space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[13px] font-semibold uppercase tracking-[0.08em] data-mono">Flota Empresa</p>
              <p className="text-[10px] text-slate-500">{summary?.total || 0} vehículos</p>
            </div>
            <button onClick={startCreate} className="control-btn px-2.5 py-1.5 rounded-md text-[11px] flex items-center gap-1.5">
              <Plus size={12} />
              Nuevo
            </button>
          </div>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar por código, matrícula..."
            className="w-full px-3 py-2 text-[12px] bg-white/[0.03] border border-white/[0.08] rounded-[10px] focus:outline-none focus:border-cyan-500/40"
          />
          <div className="grid grid-cols-4 gap-1 text-[10px] data-mono">
            <div className="rounded-md bg-emerald-500/[0.12] text-emerald-300 px-2 py-1 text-center">{summary?.active ?? 0} A</div>
            <div className="rounded-md bg-amber-500/[0.12] text-amber-300 px-2 py-1 text-center">{summary?.maintenance ?? 0} T</div>
            <div className="rounded-md bg-slate-500/[0.15] text-slate-300 px-2 py-1 text-center">{summary?.inactive ?? 0} I</div>
            <div className="rounded-md bg-cyan-500/[0.12] text-cyan-300 px-2 py-1 text-center">{summary?.total_seats_max ?? 0}P</div>
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2">
          {loading && <p className="text-[11px] text-slate-500">Cargando flota...</p>}
          {!loading && filteredVehicles.length === 0 && (
            <p className="text-[11px] text-slate-500">No hay vehículos registrados</p>
          )}
          {filteredVehicles.map((v) => {
            const selected = String(v.id) === String(selectedId);
            return (
              <button
                key={v.id}
                onClick={() => {
                  setSelectedId(v.id);
                  if (!isEditing) setForm(fromVehicle(v));
                }}
                className={`w-full text-left p-3 rounded-[12px] border transition-all ${
                  selected ? 'border-cyan-500/40 bg-cyan-500/[0.08]' : 'border-white/[0.08] hover:border-white/[0.2] bg-white/[0.02]'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[12px] font-semibold data-mono">{v.vehicle_code}</p>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-white/[0.06] text-slate-300">{v.seats_min}-{v.seats_max}P</span>
                </div>
                <p className="text-[11px] text-slate-300 mt-1 data-mono">{v.plate}</p>
                <p className="text-[10px] text-slate-500 mt-1">{v.brand || 'Marca'} {v.model || ''}</p>
              </button>
            );
          })}
        </div>
      </aside>

      <section className="control-panel rounded-[16px] p-4 overflow-y-auto min-h-0">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-[14px] font-semibold uppercase tracking-[0.08em] data-mono">Perfil de Vehículo</p>
            <p className="text-[11px] text-slate-500">Datos operativos y documentación base</p>
          </div>
          <div className="flex items-center gap-2">
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
                <button onClick={handleSave} disabled={saving} className="control-btn px-3 py-1.5 rounded-md text-[11px] flex items-center gap-1.5 disabled:opacity-50">
                  <Save size={12} />
                  {saving ? 'Guardando...' : 'Guardar'}
                </button>
              </>
            )}
          </div>
        </div>

        {!selectedVehicle && !isEditing && (
          <div className="h-[65vh] border border-dashed border-white/[0.15] rounded-[14px] flex items-center justify-center">
            <div className="text-center">
              <Bus className="mx-auto mb-2 text-slate-500" size={24} />
              <p className="text-[12px] text-slate-400">Selecciona un vehículo o crea uno nuevo</p>
            </div>
          </div>
        )}

        {(selectedVehicle || isEditing) && (
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-3">
              <label className="space-y-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Código</span>
                <input value={activeForm.vehicle_code} disabled={!isEditing} onChange={(e) => setForm((p) => ({ ...p, vehicle_code: e.target.value }))} className="w-full px-3 py-2 text-[12px] rounded-md bg-[#0f1723] border border-white/[0.1] disabled:opacity-70" />
              </label>
              <label className="space-y-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Matrícula</span>
                <input value={activeForm.plate} disabled={!isEditing} onChange={(e) => setForm((p) => ({ ...p, plate: e.target.value }))} className="w-full px-3 py-2 text-[12px] rounded-md bg-[#0f1723] border border-white/[0.1] disabled:opacity-70 data-mono" />
              </label>
              <label className="space-y-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Marca</span>
                <input value={activeForm.brand} disabled={!isEditing} onChange={(e) => setForm((p) => ({ ...p, brand: e.target.value }))} className="w-full px-3 py-2 text-[12px] rounded-md bg-[#0f1723] border border-white/[0.1] disabled:opacity-70" />
              </label>
              <label className="space-y-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Modelo</span>
                <input value={activeForm.model} disabled={!isEditing} onChange={(e) => setForm((p) => ({ ...p, model: e.target.value }))} className="w-full px-3 py-2 text-[12px] rounded-md bg-[#0f1723] border border-white/[0.1] disabled:opacity-70" />
              </label>
              <label className="space-y-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Año</span>
                <input type="number" value={activeForm.year} disabled={!isEditing} onChange={(e) => setForm((p) => ({ ...p, year: e.target.value }))} className="w-full px-3 py-2 text-[12px] rounded-md bg-[#0f1723] border border-white/[0.1] disabled:opacity-70" />
              </label>
              <label className="space-y-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Estado</span>
                <select value={activeForm.status} disabled={!isEditing} onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))} className="w-full px-3 py-2 text-[12px] rounded-md bg-[#0f1723] border border-white/[0.1] disabled:opacity-70">
                  <option value="active">Activo</option>
                  <option value="maintenance">Taller</option>
                  <option value="inactive">Inactivo</option>
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Plazas mín.</span>
                <input type="number" value={activeForm.seats_min} disabled={!isEditing} onChange={(e) => setForm((p) => ({ ...p, seats_min: e.target.value }))} className="w-full px-3 py-2 text-[12px] rounded-md bg-[#0f1723] border border-white/[0.1] disabled:opacity-70" />
              </label>
              <label className="space-y-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Plazas máx.</span>
                <input type="number" value={activeForm.seats_max} disabled={!isEditing} onChange={(e) => setForm((p) => ({ ...p, seats_max: e.target.value }))} className="w-full px-3 py-2 text-[12px] rounded-md bg-[#0f1723] border border-white/[0.1] disabled:opacity-70" />
              </label>
              <label className="space-y-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Combustible</span>
                <input value={activeForm.fuel_type} disabled={!isEditing} onChange={(e) => setForm((p) => ({ ...p, fuel_type: e.target.value }))} className="w-full px-3 py-2 text-[12px] rounded-md bg-[#0f1723] border border-white/[0.1] disabled:opacity-70" />
              </label>
              <label className="space-y-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Kilometraje</span>
                <input type="number" value={activeForm.mileage_km} disabled={!isEditing} onChange={(e) => setForm((p) => ({ ...p, mileage_km: e.target.value }))} className="w-full px-3 py-2 text-[12px] rounded-md bg-[#0f1723] border border-white/[0.1] disabled:opacity-70" />
              </label>
            </div>

            <label className="flex items-center gap-2 text-[12px] text-slate-300">
              <input type="checkbox" checked={!!activeForm.accessibility} disabled={!isEditing} onChange={(e) => setForm((p) => ({ ...p, accessibility: e.target.checked }))} />
              Accesible PMR
            </label>

            <label className="space-y-1 block">
              <span className="text-[10px] text-slate-500 uppercase tracking-[0.08em]">Notas</span>
              <textarea value={activeForm.notes || ''} disabled={!isEditing} onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))} rows={3} className="w-full px-3 py-2 text-[12px] rounded-md bg-[#0f1723] border border-white/[0.1] disabled:opacity-70" />
            </label>

            <div className="border border-white/[0.08] rounded-[12px] p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <FileText size={14} className="text-cyan-300" />
                  <p className="text-[12px] font-semibold uppercase tracking-[0.08em]">Documentación</p>
                </div>
                {isEditing && (
                  <button onClick={addDocument} className="control-btn px-2 py-1 rounded-md text-[10px]">Añadir documento</button>
                )}
              </div>
              <div className="space-y-2">
                {(activeForm.documents || []).length === 0 && (
                  <p className="text-[11px] text-slate-500">Sin documentos registrados</p>
                )}
                {(activeForm.documents || []).map((doc, idx) => (
                  <div key={`${doc.id || 'doc'}-${idx}`} className="grid grid-cols-[1fr_1fr_130px_130px_36px] gap-2">
                    <input value={doc.doc_type || ''} disabled={!isEditing} onChange={(e) => updateDocument(idx, 'doc_type', e.target.value)} placeholder="Tipo" className="px-2 py-1.5 text-[11px] rounded-md bg-[#0f1723] border border-white/[0.1]" />
                    <input value={doc.reference || ''} disabled={!isEditing} onChange={(e) => updateDocument(idx, 'reference', e.target.value)} placeholder="Referencia" className="px-2 py-1.5 text-[11px] rounded-md bg-[#0f1723] border border-white/[0.1]" />
                    <input type="date" value={doc.issue_date || ''} disabled={!isEditing} onChange={(e) => updateDocument(idx, 'issue_date', e.target.value)} className="px-2 py-1.5 text-[11px] rounded-md bg-[#0f1723] border border-white/[0.1]" />
                    <input type="date" value={doc.expiry_date || ''} disabled={!isEditing} onChange={(e) => updateDocument(idx, 'expiry_date', e.target.value)} className="px-2 py-1.5 text-[11px] rounded-md bg-[#0f1723] border border-white/[0.1]" />
                    <button disabled={!isEditing} onClick={() => removeDocument(idx)} className="border border-red-500/30 text-red-300 rounded-md hover:bg-red-500/[0.08] disabled:opacity-40">
                      <Trash2 size={12} className="mx-auto" />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {!isEditing && selectedVehicle && (
              <div className="text-[11px] text-slate-500 data-mono">
                <span className="mr-3">Estado: {STATUS_LABEL[selectedVehicle.status] || selectedVehicle.status}</span>
                <span className="mr-3">Edad: {selectedVehicle.age_years ?? '-'} años</span>
                <span>Actualizado: {selectedVehicle.updated_at?.slice(0, 19).replace('T', ' ') || '-'}</span>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

