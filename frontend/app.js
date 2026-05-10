const app = {
  apiUrl: localStorage.getItem('billing_api_url') || 'http://localhost:8502',
  apiKey: localStorage.getItem('billing_api_key') || '',
  clientes: [],
  presupuestos: [],
  prefacturas: [],
  cobros: [],

  async init() {
    // Auto-detectar URL del servidor basada en window.location
    const detected = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8502';
    this.apiUrl = localStorage.getItem('billing_api_url') || detected;
    this.apiKey = localStorage.getItem('billing_api_key') || '';
    if (this.apiKey) {
      // Validar key antes de mostrar app
      try {
        const res = await fetch(this.apiUrl + '/api/health', { headers: { 'X-API-Key': this.apiKey } });
        if (res.ok) {
          this.showApp();
          this.loadDashboard();
        } else {
          // Key invalida, limpiar
          this.logout();
        }
      } catch (e) {
        this.logout();
      }
    } else {
      this.showLogin();
      const inputUrl = document.getElementById('api-url');
      if (inputUrl) inputUrl.value = this.apiUrl;
    }
    document.getElementById('btn-login').addEventListener('click', () => this.login());
    document.getElementById('btn-logout').addEventListener('click', () => this.logout());
    document.getElementById('api-key').addEventListener('keydown', e => { if (e.key === 'Enter') this.login(); });
    document.querySelectorAll('.nav-item').forEach(el => el.addEventListener('click', e => {
      e.preventDefault();
      const section = el.dataset.section;
      this.navigate(section);
    }));
  },

  async api(method, path, body = null) {
    const url = this.apiUrl + path;
    const opts = { method, headers: { 'X-API-Key': this.apiKey, 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    try {
      const res = await fetch(url, opts);
      if (res.status === 429) throw new Error('Demasiadas solicitudes. Espere un momento.');
      if (res.status === 401 || res.status === 403) {
        // Key invalida: limpiar y redirigir al login
        this.logout();
        throw new Error('Sesión expirada. Ingrese nuevamente.');
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `Error ${res.status}`);
      }
      if (res.status === 204) return null;
      return await res.json();
    } catch (e) {
      this.alert('error', e.message);
      throw e;
    }
  },

  async login() {
    this.apiKey = document.getElementById('api-key').value.trim();
    this.apiUrl = document.getElementById('api-url').value.trim().replace(/\/$/, '');
    if (!this.apiKey) { document.getElementById('login-error').textContent = 'Ingrese la API Key'; return; }
    // Validar key antes de guardar
    try {
      const res = await fetch(this.apiUrl + '/api/health', { headers: { 'X-API-Key': this.apiKey } });
      if (!res.ok) {
        document.getElementById('login-error').textContent = 'API Key inválida o servidor no responde';
        return;
      }
    } catch (e) {
      document.getElementById('login-error').textContent = 'No se pudo conectar al servidor: ' + e.message;
      return;
    }
    localStorage.setItem('billing_api_key', this.apiKey);
    localStorage.setItem('billing_api_url', this.apiUrl);
    this.showApp();
    this.loadDashboard();
  },

  logout() {
    localStorage.removeItem('billing_api_key');
    localStorage.removeItem('billing_api_url');
    this.apiKey = '';
    this.showLogin();
    // Limpiar alerts y modales
    document.getElementById('alerts').innerHTML = '';
    document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'));
    document.getElementById('modal-overlay').classList.add('hidden');
  },

  showLogin() {
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('app-screen').classList.add('hidden');
    document.getElementById('login-error').textContent = '';
  },

  showApp() {
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('app-screen').classList.remove('hidden');
  },

  navigate(section) {
    document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
    document.getElementById(section).classList.remove('hidden');
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelector(`.nav-item[data-section="${section}"]`).classList.add('active');
    const titles = { dashboard: 'Dashboard', clientes: 'Clientes Fiscales', presupuestos: 'Presupuestos', prefacturas: 'Pre-facturas', cobros: 'Historial de Cobros', reportes: 'Reportes Contador' };
    document.getElementById('page-title').textContent = titles[section];
    if (section === 'clientes') this.loadClientes();
    if (section === 'presupuestos') this.loadPresupuestos();
    if (section === 'prefacturas') this.loadPrefacturas();
    if (section === 'cobros') this.loadCobros();
    if (section === 'reportes') this.loadReportes();
  },

  alert(type, msg) {
    const div = document.createElement('div');
    div.className = `alert alert-${type}`;
    div.textContent = msg;
    document.getElementById('alerts').appendChild(div);
    setTimeout(() => div.remove(), 4000);
  },

  // ── Dashboard ──
  async loadDashboard() {
    try {
      const metrics = await this.api('GET', '/api/metrics');
      document.getElementById('dash-clientes').textContent = metrics.clientes;
      document.getElementById('dash-presupuestos').textContent = metrics.presupuestos;
      document.getElementById('dash-prefacturas').textContent = metrics.prefacturas;
      document.getElementById('dash-cobros').textContent = metrics.cobros;
      document.getElementById('dash-pendientes').textContent = metrics.estados_pago;
    } catch (e) {}
    try {
      const health = await this.api('GET', '/api/health');
      document.getElementById('dash-arca-ready').textContent = health.arca_ready ? 'Sí' : 'No';
      document.getElementById('arca-badge').textContent = 'ARCA: ' + (health.arca_modo === 'homologacion' ? 'Homologación' : 'Producción');
    } catch (e) {}
  },

  // ── Clientes ──
  async loadClientes() {
    const data = await this.api('GET', '/api/clientes/');
    this.clientes = data.data || [];
    this.renderClientes(this.clientes);
  },

  renderClientes(list) {
    const tbody = document.getElementById('tabla-clientes');
    tbody.innerHTML = list.map(c => `
      <tr>
        <td><strong>${esc(c.nombre)}</strong></td>
        <td>${esc(c.cuit || '-')}</td>
        <td>${esc(c.dni || '-')}</td>
        <td>${esc(c.condicion_iva)}</td>
        <td>${esc(c.email || '-')}</td>
        <td class="actions">
          <button class="action-btn action-edit" onclick="app.editarCliente('${c.id}')">Editar</button>
          <button class="action-btn action-delete" onclick="app.eliminarCliente('${c.id}')">Eliminar</button>
        </td>
      </tr>
    `).join('') || '<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:24px">Sin clientes registrados</td></tr>';
  },

  searchClientes() {
    const q = document.getElementById('search-clientes').value.toLowerCase();
    const filtered = this.clientes.filter(c => (c.nombre||'').toLowerCase().includes(q) || (c.cuit||'').includes(q) || (c.dni||'').includes(q));
    this.renderClientes(filtered);
  },

  async guardarCliente() {
    const id = document.getElementById('cliente-id').value;
    const body = {
      nombre: document.getElementById('cliente-nombre').value,
      cuit: document.getElementById('cliente-cuit').value,
      dni: document.getElementById('cliente-dni').value,
      condicion_iva: document.getElementById('cliente-iva').value,
      telefono: document.getElementById('cliente-telefono').value,
      email: document.getElementById('cliente-email').value,
      direccion: document.getElementById('cliente-direccion').value,
      notas: document.getElementById('cliente-notas').value,
      empresa_id: 'default'
    };
    try {
      if (id) {
        await this.api('PUT', `/api/clientes/${id}`, body);
        this.alert('success', 'Cliente actualizado');
      } else {
        await this.api('POST', '/api/clientes/', body);
        this.alert('success', 'Cliente creado');
      }
      this.closeModal('cliente-modal');
      this.loadClientes();
      this.loadDashboard();
    } catch (e) {}
  },

  editarCliente(id) {
    const c = this.clientes.find(x => x.id === id);
    if (!c) return;
    document.getElementById('cliente-id').value = c.id;
    document.getElementById('cliente-nombre').value = c.nombre;
    document.getElementById('cliente-cuit').value = c.cuit;
    document.getElementById('cliente-dni').value = c.dni;
    document.getElementById('cliente-iva').value = c.condicion_iva;
    document.getElementById('cliente-telefono').value = c.telefono;
    document.getElementById('cliente-email').value = c.email;
    document.getElementById('cliente-direccion').value = c.direccion;
    document.getElementById('cliente-notas').value = c.notas;
    document.getElementById('cliente-modal-title').textContent = 'Editar Cliente';
    this.openModal('cliente-modal');
  },

  async eliminarCliente(id) {
    if (!confirm('Eliminar cliente?')) return;
    try { await this.api('DELETE', `/api/clientes/${id}`); this.alert('success', 'Cliente eliminado'); this.loadClientes(); this.loadDashboard(); } catch (e) {}
  },

  // ── Presupuestos ──
  async loadPresupuestos() {
    const data = await this.api('GET', '/api/presupuestos/');
    this.presupuestos = data.data || [];
    const tbody = document.getElementById('tabla-presupuestos');
    tbody.innerHTML = this.presupuestos.map(p => `
      <tr>
        <td><strong>${esc(p.numero)}</strong></td>
        <td>${esc(p.cliente_nombre)}</td>
        <td>${esc(p.fecha ? p.fecha.slice(0,10) : '-')}</td>
        <td><span class="estado-badge est-${p.estado.toLowerCase().replace(/ /g,'')}">${esc(p.estado)}</span></td>
        <td><strong>${esc(p.total_fmt || '')}</strong></td>
        <td class="actions">
          <button class="action-btn action-edit" onclick="app.verPresupuesto('${p.id}')">Ver</button>
          <button class="action-btn action-cae" onclick="app.convertirPresupuesto('${p.id}')" ${p.estado !== 'Aceptado' && p.estado !== 'Enviado' ? 'disabled style=opacity:0.5' : ''}>Convertir</button>
          <button class="action-btn action-delete" onclick="app.eliminarPresupuesto('${p.id}')">Eliminar</button>
        </td>
      </tr>
    `).join('') || '<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:24px">Sin presupuestos</td></tr>';
  },

  addPresItem() {
    const div = document.createElement('div');
    div.className = 'item-row';
    div.innerHTML = `<input type="text" placeholder="Concepto" class="item-concepto"><input type="number" placeholder="Cantidad" class="item-cant" value="1" min="1"><input type="number" placeholder="Precio" class="item-precio"><button class="btn-remove" onclick="this.parentElement.remove()">&times;</button>`;
    document.getElementById('pres-items').appendChild(div);
  },

  async guardarPresupuesto() {
    const items = [];
    document.querySelectorAll('#pres-items .item-row').forEach(row => {
      const c = row.querySelector('.item-concepto').value;
      const q = parseInt(row.querySelector('.item-cant').value) || 1;
      const p = parseFloat(row.querySelector('.item-precio').value) || 0;
      if (c) items.push({ concepto: c, cantidad: q, precio_unitario: p });
    });
    const body = {
      empresa_id: 'default',
      cliente_id: document.getElementById('pres-cliente-id').value,
      cliente_nombre: document.getElementById('pres-cliente-nombre').value,
      notas: document.getElementById('pres-notas').value,
      items
    };
    try { await this.api('POST', '/api/presupuestos/', body); this.alert('success', 'Presupuesto creado'); this.closeModal('presupuesto-modal'); this.loadPresupuestos(); this.loadDashboard(); } catch (e) {}
  },

  verPresupuesto(id) { const p = this.presupuestos.find(x => x.id === id); if (p) alert(JSON.stringify(p, null, 2)); },
  async convertirPresupuesto(id) { try { await this.api('POST', `/api/presupuestos/${id}/convertir`); this.alert('success', 'Convertido a pre-factura'); this.loadPresupuestos(); } catch (e) {} },
  async eliminarPresupuesto(id) { if (!confirm('Eliminar?')) return; try { await this.api('DELETE', `/api/presupuestos/${id}`); this.alert('success', 'Eliminado'); this.loadPresupuestos(); this.loadDashboard(); } catch (e) {} },

  // ── Pre-facturas ──
  async loadPrefacturas() {
    const data = await this.api('GET', '/api/prefacturas/');
    this.prefacturas = data.data || [];
    const tbody = document.getElementById('tabla-prefacturas');
    tbody.innerHTML = this.prefacturas.map(f => `
      <tr>
        <td><strong>${esc(f.numero)}</strong></td>
        <td>${esc(f.cliente_nombre)}</td>
        <td>${esc(f.fecha ? f.fecha.slice(0,10) : '-')}</td>
        <td><span class="estado-badge est-${f.estado.toLowerCase().replace(/ /g,'').replace('_arca','')}">${esc(f.estado)}</span></td>
        <td>${esc(f.cae || '-')}</td>
        <td><strong>${esc(f.total_fmt || '')}</strong></td>
        <td class="actions">
          <button class="action-btn action-cae" onclick="app.solicitarCae('${f.id}')" ${f.estado !== 'Pendiente' && f.estado !== 'Rechazada_ARCA' ? 'disabled style=opacity:0.5' : ''}>Solicitar CAE</button>
          <button class="action-btn action-delete" onclick="app.eliminarPrefactura('${f.id}')">Eliminar</button>
        </td>
      </tr>
    `).join('') || '<tr><td colspan="7" style="text-align:center;color:#94a3b8;padding:24px">Sin pre-facturas</td></tr>';
  },

  addFacItem() {
    const div = document.createElement('div'); div.className = 'item-row';
    div.innerHTML = `<input type="text" placeholder="Concepto" class="item-concepto"><input type="number" placeholder="Cantidad" class="item-cant" value="1" min="1"><input type="number" placeholder="Precio" class="item-precio"><button class="btn-remove" onclick="this.parentElement.remove()">&times;</button>`;
    document.getElementById('fac-items').appendChild(div);
  },

  async guardarPrefactura() {
    const items = [];
    document.querySelectorAll('#fac-items .item-row').forEach(row => {
      const c = row.querySelector('.item-concepto').value;
      const q = parseInt(row.querySelector('.item-cant').value) || 1;
      const p = parseFloat(row.querySelector('.item-precio').value) || 0;
      if (c) items.push({ concepto: c, cantidad: q, precio_unitario: p });
    });
    const body = {
      empresa_id: 'default',
      cliente_id: document.getElementById('fac-cliente-id').value,
      cliente_nombre: document.getElementById('fac-cliente-nombre').value,
      notas: document.getElementById('fac-notas').value,
      items
    };
    try { await this.api('POST', '/api/prefacturas/', body); this.alert('success', 'Pre-factura creada'); this.closeModal('prefactura-modal'); this.loadPrefacturas(); this.loadDashboard(); } catch (e) {}
  },

  async solicitarCae(id) {
    try {
      const res = await this.api('POST', `/api/prefacturas/${id}/solicitar-cae`);
      this.alert('info', res.mensaje + (res.modo ? ` (${res.modo})` : ''));
      setTimeout(() => this.loadPrefacturas(), 800);
    } catch (e) {}
  },

  async eliminarPrefactura(id) { if (!confirm('Eliminar?')) return; try { await this.api('DELETE', `/api/prefacturas/${id}`); this.alert('success', 'Eliminado'); this.loadPrefacturas(); this.loadDashboard(); } catch (e) {} },

  // ── Cobros ──
  async loadCobros() {
    const data = await this.api('GET', '/api/cobros/');
    this.cobros = data.data || [];
    const tbody = document.getElementById('tabla-cobros');
    tbody.innerHTML = this.cobros.map(c => `
      <tr>
        <td>${esc(c.fecha ? c.fecha.slice(0,10) : '-')}</td>
        <td>${esc(c.cliente_nombre)}</td>
        <td><strong>${esc(c.monto_fmt || c.monto)}</strong></td>
        <td>${esc(c.metodo_pago)}</td>
        <td>${esc(c.referencia || '-')}</td>
        <td class="actions">
          <button class="action-btn action-delete" onclick="app.eliminarCobro('${c.id}')">Eliminar</button>
        </td>
      </tr>
    `).join('') || '<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:24px">Sin cobros registrados</td></tr>';
  },

  async guardarCobro() {
    const body = {
      empresa_id: 'default',
      cliente_id: document.getElementById('cobro-cliente-id').value,
      cliente_nombre: document.getElementById('cobro-cliente-nombre').value,
      prefactura_id: document.getElementById('cobro-prefactura-id').value,
      monto: parseFloat(document.getElementById('cobro-monto').value) || 0,
      metodo_pago: document.getElementById('cobro-metodo').value,
      referencia: document.getElementById('cobro-referencia').value,
      notas: document.getElementById('cobro-notas').value,
    };
    try { await this.api('POST', '/api/cobros/', body); this.alert('success', 'Cobro registrado'); this.closeModal('cobro-modal'); this.loadCobros(); this.loadDashboard(); } catch (e) {}
  },

  async eliminarCobro(id) { if (!confirm('Eliminar?')) return; try { await this.api('DELETE', `/api/cobros/${id}`); this.alert('success', 'Eliminado'); this.loadCobros(); this.loadDashboard(); } catch (e) {} },

  // ── Reportes ──
  async loadReportes() {
    try {
      const cobros = await this.api('GET', '/api/cobros/resumen/mensual?empresa_id=default');
      const container = document.getElementById('reporte-cobros');
      const meses = cobros.meses || {};
      const keys = Object.keys(meses).sort().reverse().slice(0, 6);
      if (!keys.length) { container.innerHTML = '<p style="color:#94a3b8">Sin datos</p>'; return; }
      container.innerHTML = '<div class="bars">' + keys.map(k => {
        const m = meses[k]; const max = Math.max(...Object.values(meses).map(x => x.total)); const pct = max ? (m.total / max * 100) : 0;
        return `<div class="bar-row"><div class="bar-label">${k}</div><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div><div class="bar-value">$${m.total.toLocaleString('es-AR')}</div></div>`;
      }).join('') + '</div>';
    } catch (e) {}
    try {
      const cartera = await this.api('GET', '/api/estados/resumen/cartera?empresa_id=default');
      const container = document.getElementById('reporte-cartera');
      const estados = cartera.por_estado || {};
      container.innerHTML = '<div class="bars">' + Object.entries(estados).map(([k, v]) => {
        return `<div class="bar-row"><div class="bar-label">${k}</div><div class="bar-track"><div class="bar-fill" style="width:100%"></div></div><div class="bar-value">${v.cantidad} — $${v.monto_total.toLocaleString('es-AR')}</div></div>`;
      }).join('') + '</div>';
    } catch (e) {}
  },

  // ── Modals ──
  openModal(id) { document.getElementById('modal-overlay').classList.remove('hidden'); document.getElementById(id).classList.remove('hidden'); },
  closeModal(id) { document.getElementById(id).classList.add('hidden'); if (!document.querySelectorAll('.modal:not(.hidden)').length) document.getElementById('modal-overlay').classList.add('hidden'); },
  closeAllModals(e) { if (e.target.id === 'modal-overlay') { document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden')); document.getElementById('modal-overlay').classList.add('hidden'); } }
};

function esc(s) {
  const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML;
}

document.addEventListener('DOMContentLoaded', () => app.init());
