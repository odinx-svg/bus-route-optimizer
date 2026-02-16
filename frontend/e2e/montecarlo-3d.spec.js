import { test, expect } from '@playwright/test';

/**
 * Test E2E: Monte Carlo 3D Visualization
 * 
 * Para ejecutar (desde frontend/):
 *   npx playwright test e2e/montecarlo-3d.spec.js --headed
 * 
 * O modo UI (interactivo):
 *   npx playwright test --ui
 */

test.describe('Monte Carlo 3D', () => {
  
  test.beforeEach(async ({ page }) => {
    // Navegar a la app
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');
  });
  
  async function uploadAndOptimize(page) {
    // 1. Subir archivos reales de rutas
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles([
      'e2e/test-data/UE3617.xlsx',
      'e2e/test-data/UE3618.xlsx'
    ]);
    await page.waitForTimeout(1000);
    
    // 2. Click en "Subir X archivos"
    await page.click('button:has-text("Subir")');
    await page.waitForTimeout(3000);
    await page.waitForTimeout(2000);
    
    // 3. Click en Optimizar
    await page.click('button:has-text("Optimizar")');
    await page.waitForTimeout(5000);
    
    // 4. Esperar a que termine (aparezcan las pestañas)
    await page.waitForSelector('button:has-text("Mapa")', { timeout: 30000 });
  }

  test('debería mostrar pestaña Monte Carlo 3D', async ({ page }) => {
    // Subir y optimizar
    await uploadAndOptimize(page);
    
    // 3. Verificar que existe la pestaña Monte Carlo 3D
    const monteCarloTab = page.locator('button:has-text("Monte Carlo 3D")');
    await expect(monteCarloTab).toBeVisible();
    
    // Hacer screenshot
    await page.screenshot({ path: 'e2e/screenshots/01-tabs-visible.png' });
  });

  test('debería abrir panel Monte Carlo 3D', async ({ page }) => {
    // Subir y optimizar
    await uploadAndOptimize(page);
    
    // Click en pestaña Monte Carlo
    await page.click('button:has-text("Monte Carlo 3D")');
    await page.waitForTimeout(500);
    
    // Verificar que el panel se muestra
    const panel = page.locator('text=Validación Monte Carlo 3D');
    await expect(panel).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/02-montecarlo-panel.png' });
  });

  test('debería iniciar simulación y mostrar visualización 3D', async ({ page }) => {
    // Subir y optimizar
    await uploadAndOptimize(page);
    
    // Abrir Monte Carlo
    await page.click('button:has-text("Monte Carlo 3D")');
    await page.waitForTimeout(500);
    
    // Verificar estado inicial
    const initialState = page.locator('text=Configura y presiona');
    await expect(initialState).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/03-initial-state.png' });
    
    // Click en Iniciar Simulación
    await page.click('button:has-text("Iniciar Simulación")');
    
    // Esperar a que empiece
    await page.waitForTimeout(1000);
    
    // Verificar que el canvas 3D está presente (buscamos el contenedor)
    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/04-simulation-running.png' });
    
    // Esperar unos segundos para acumular simulaciones
    await page.waitForTimeout(5000);
    
    // Verificar progreso
    const progressText = page.locator('text=Simulaciones:');
    await expect(progressText).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/05-simulation-progress.png', fullPage: true });
    
    // Esperar a completar o detener manualmente
    await page.waitForTimeout(5000);
    
    await page.screenshot({ path: 'e2e/screenshots/06-simulation-advanced.png', fullPage: true });
  });

  test('debería permitir configurar simulación', async ({ page }) => {
    // Subir y optimizar
    await uploadAndOptimize(page);
    
    // Abrir Monte Carlo
    await page.click('button:has-text("Monte Carlo 3D")');
    await page.waitForTimeout(500);
    
    // Click en botón de configuración
    await page.click('button:has(Settings2)');
    
    // Verificar controles de configuración
    const simCount = page.locator('label:has-text("Simulaciones")');
    await expect(simCount).toBeVisible();
    
    const uncertaintySlider = page.locator('input[type="range"]');
    await expect(uncertaintySlider).toBeVisible();
    
    // Cambiar número de simulaciones
    const simInput = page.locator('input[type="number"]');
    await simInput.fill('500');
    
    await page.screenshot({ path: 'e2e/screenshots/07-config-panel.png' });
    
    // Cerrar configuración (click fuera o en botón otra vez)
    await page.click('button:has(Settings2)');
    
    // Iniciar con nueva configuración
    await page.click('button:has-text("Iniciar Simulación")');
    await page.waitForTimeout(2000);
    
    await page.screenshot({ path: 'e2e/screenshots/08-custom-config-running.png' });
  });

  test('debería mostrar controles 3D (rotar/pausar)', async ({ page }) => {
    // Subir y optimizar
    await uploadAndOptimize(page);
    
    // Abrir Monte Carlo y empezar
    await page.click('button:has-text("Monte Carlo 3D")');
    await page.waitForTimeout(500);
    await page.click('button:has-text("Iniciar Simulación")');
    await page.waitForTimeout(2000);
    
    // Verificar botón de pausar rotación
    const pauseBtn = page.locator('button:has-text("Pausar")');
    await expect(pauseBtn).toBeVisible();
    
    // Click para pausar
    await pauseBtn.click();
    await page.waitForTimeout(500);
    
    // Verificar que cambió a "Rotar"
    const rotateBtn = page.locator('button:has-text("Rotar")');
    await expect(rotateBtn).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/09-paused-rotation.png' });
  });

  test('debería mostrar leyenda correctamente', async ({ page }) => {
    // Subir y optimizar
    await uploadAndOptimize(page);
    
    // Abrir Monte Carlo
    await page.click('button:has-text("Monte Carlo 3D")');
    
    // Verificar leyenda
    const factible = page.locator('text=Factible');
    const noFactible = page.locator('text=No factible');
    
    await expect(factible).toBeVisible();
    await expect(noFactible).toBeVisible();
    
    // Verificar puntos de colores en leyenda
    const greenDot = page.locator('.bg-green-500');
    const redDot = page.locator('.bg-red-500');
    
    await expect(greenDot).toBeVisible();
    await expect(redDot).toBeVisible();
  });
});
