import { test, expect } from '@playwright/test';

const NOW = new Date().toISOString();

const buildWorkspaceList = () => {
  const primary = {
    id: 'ws-main',
    name: 'Vigo Operativo',
    city_label: 'Vigo',
    status: 'active',
    archived: false,
    working_version_number: 3,
    published_version_number: 2,
    summary_metrics: {
      best_buses: 40,
      infeasible_buses: 0,
      total_buses: 40,
    },
    created_at: NOW,
    updated_at: NOW,
  };

  const extra = Array.from({ length: 18 }).map((_, idx) => ({
    id: `ws-extra-${idx + 1}`,
    name: `Optimizacion ${idx + 1}`,
    city_label: idx % 2 === 0 ? 'Vigo' : 'Mos',
    status: idx % 4 === 0 ? 'draft' : 'active',
    archived: false,
    working_version_number: 1,
    published_version_number: idx % 4 === 0 ? null : 1,
    summary_metrics: {
      best_buses: 20 + idx,
      infeasible_buses: 0,
      total_buses: 20 + idx,
    },
    created_at: NOW,
    updated_at: NOW,
  }));

  return [primary, ...extra];
};

const workspaceDetail = {
  id: 'ws-main',
  name: 'Vigo Operativo',
  city_label: 'Vigo',
  status: 'active',
  archived: false,
  published_version_id: 'ver-2',
  working_version_id: 'ver-3',
  working_version_number: 3,
  published_version_number: 2,
  created_at: NOW,
  updated_at: NOW,
  working_version: {
    id: 'ver-3',
    workspace_id: 'ws-main',
    version_number: 3,
    save_kind: 'save',
    routes_payload: [
      {
        id: 'R-L-001',
        route_id: 'R-L-001',
        type: 'entry',
        school_name: 'IES Vigo',
        departure_time: '07:30',
        arrival_time: '08:10',
        stops: [
          { name: 'Praza A', lat: 42.24, lon: -8.72, order: 1, time_from_start: 0 },
          { name: 'IES Vigo', lat: 42.25, lon: -8.73, order: 2, time_from_start: 40, is_school: true },
        ],
      },
      {
        id: 'R-L-002',
        route_id: 'R-L-002',
        type: 'exit',
        school_name: 'IES Vigo',
        departure_time: '14:10',
        arrival_time: '14:45',
        stops: [
          { name: 'IES Vigo', lat: 42.25, lon: -8.73, order: 1, time_from_start: 0, is_school: true },
          { name: 'Praza A', lat: 42.24, lon: -8.72, order: 2, time_from_start: 35 },
        ],
      },
    ],
    schedule_by_day: {
      L: {
        schedule: [
          {
            bus_id: 'B001',
            items: [
              {
                route_id: 'R-L-001',
                route_code: 'R-L-001',
                start_time: '07:30',
                end_time: '08:10',
                type: 'entry',
                origin: 'Praza A',
                destination: 'IES Vigo',
                school_name: 'IES Vigo',
              },
              {
                route_id: 'R-L-002',
                route_code: 'R-L-002',
                start_time: '14:10',
                end_time: '14:45',
                type: 'exit',
                origin: 'IES Vigo',
                destination: 'Praza A',
                school_name: 'IES Vigo',
              },
            ],
          },
        ],
        stats: {
          total_buses: 1,
          total_entries: 1,
          total_exits: 1,
          avg_routes_per_bus: 2,
        },
      },
      M: { schedule: [], stats: { total_buses: 0, total_entries: 0, total_exits: 0, avg_routes_per_bus: 0 } },
      Mc: { schedule: [], stats: { total_buses: 0, total_entries: 0, total_exits: 0, avg_routes_per_bus: 0 } },
      X: { schedule: [], stats: { total_buses: 0, total_entries: 0, total_exits: 0, avg_routes_per_bus: 0 } },
      V: { schedule: [], stats: { total_buses: 0, total_entries: 0, total_exits: 0, avg_routes_per_bus: 0 } },
    },
    parse_report: { rows_total: 20, rows_dropped_invalid: 0 },
    validation_report: null,
    fleet_snapshot: null,
    summary_metrics: { best_buses: 1, infeasible_buses: 0, total_buses: 1 },
    created_at: NOW,
  },
  published_version: null,
};

test.describe('Control Hub + Studio smoke', () => {
  let counters = { listHits: 0, saveHits: 0, publishHits: 0 };

  test.beforeEach(async ({ page }) => {
    const workspaces = buildWorkspaceList();
    counters = { listHits: 0, saveHits: 0, publishHits: 0 };

    await page.route('**/api/workspaces/migrate-legacy', async (route) => {
      await route.fulfill({ json: { success: true, migrated: false, details: {} } });
    });

    await page.route('**/api/workspaces/preferences/last-open', async (route) => {
      await route.fulfill({ json: { success: true } });
    });

    await page.route('**/api/workspaces/preferences', async (route) => {
      await route.fulfill({ json: { last_open_workspace_id: 'ws-main' } });
    });

    await page.route('**/api/workspaces/ws-main/save', async (route) => {
      counters.saveHits += 1;
      await route.fulfill({ json: { success: true, id: `save-${counters.saveHits}` } });
    });

    await page.route('**/api/workspaces/ws-main/publish', async (route) => {
      counters.publishHits += 1;
      await route.fulfill({ json: { success: true, id: `pub-${counters.publishHits}` } });
    });

    await page.route('**/api/workspaces/ws-main', async (route) => {
      await route.fulfill({ json: workspaceDetail });
    });

    await page.route('**/api/workspaces**', async (route) => {
      const url = route.request().url();
      if (url.includes('/api/workspaces/ws-main')) {
        await route.fallback();
        return;
      }
      counters.listHits += 1;
      await route.fulfill({ json: { items: workspaces } });
    });

    await page.route('**/api/fleet/vehicles', async (route) => {
      await route.fulfill({ json: { items: [], summary: { active: 7, total: 10 } } });
    });

    await page.route('**/api/schedules/update', async (route) => {
      await route.fulfill({ json: { success: true, conflicts: [], errors: [] } });
    });

    await page.route('**/route/v1/driving/**', async (route) => {
      await route.fulfill({
        json: {
          code: 'Ok',
          routes: [{ geometry: { coordinates: [[-8.72, 42.24], [-8.73, 42.25]] } }],
        },
      });
    });

    await page.route('**/export_pdf', async (route) => {
      await route.fulfill({
        status: 200,
        headers: { 'content-type': 'application/pdf' },
        body: '%PDF-1.4\n%Mock\n',
      });
    });

    page.on('dialog', async (dialog) => {
      await dialog.accept('');
    });
  });

  test('Control es la puerta principal y dashboard hace scroll cuando toca', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await expect(page.getByText('Optimizaciones Guardadas')).toBeVisible();

    await expect(page.getByRole('button', { name: 'Control', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Studio', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: /mapa/i })).toHaveCount(0);
    await expect(page.getByRole('button', { name: /workspace/i })).toHaveCount(0);

    const hasScroll = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.control-panel'));
      const hub = cards.find((node) => node.textContent?.includes('Optimizaciones Guardadas'));
      if (!hub) return false;
      return hub.scrollHeight > hub.clientHeight;
    });
    expect(hasScroll).toBeTruthy();

    const before = counters.listHits;
    await page.getByRole('button', { name: /refrescar/i }).click();
    await expect.poll(() => counters.listHits).toBeGreaterThan(before);
  });

  test('Nueva abre ingesta en modo subida y no muestra datos antiguos', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.getByRole('button', { name: /nueva/i }).click();

    await expect(page.getByText('Ingesta')).toBeVisible();
    await expect(page.getByText(/Arrastra archivos Excel o examinar/i)).toBeVisible();
    await expect(page.getByText(/Datos cargados/i)).toHaveCount(0);
  });

  test('Studio conecta Mixto/Mapa/Workspace y Guardar/Publicar ejecutan acción', async ({ page }) => {
    await page.goto('http://localhost:5173');

    await page.getByRole('button', { name: /abrir studio/i }).first().click();
    await expect(page.getByRole('button', { name: 'Mixto', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Mapa', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Workspace', exact: true })).toBeVisible();

    await expect(page.getByText(/No hay buses pineados/i)).toBeVisible();
    await page.getByRole('button', { name: 'Workspace', exact: true }).click();
    await page.getByTitle(/Pinear bus para vista Mixto/i).first().click();
    await page.getByRole('button', { name: 'Mixto', exact: true }).click();
    await expect(page.getByText('Todas las Rutas')).toBeVisible();
    await page.getByText('B001', { exact: true }).first().click();
    await expect.poll(async () => page.getByText('Todas las Rutas').count()).toBe(0);

    await page.getByRole('button', { name: 'Mapa', exact: true }).click();
    await expect(page.getByRole('button', { name: /exportar pdf/i })).toBeVisible();

    await page.getByRole('button', { name: 'Workspace', exact: true }).click();
    const saveBefore = counters.saveHits;
    await page.getByRole('button', { name: /^guardar$/i }).first().click();
    await expect.poll(() => counters.saveHits).toBeGreaterThan(saveBefore);

    const publishBefore = counters.publishHits;
    await page.getByRole('button', { name: /^publicar$/i }).first().click();
    await expect.poll(() => counters.publishHits).toBeGreaterThan(publishBefore);
  });
});
