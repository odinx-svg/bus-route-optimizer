import { useState, useEffect, useCallback } from 'react';

export function useMonteCarlo3D(schedule) {
  const [scenarios, setScenarios] = useState([]);
  const [progress, setProgress] = useState(null);
  const [grade, setGrade] = useState(null);
  const [status, setStatus] = useState('idle'); // idle, running, completed, error
  const [ws, setWs] = useState(null);

  const startSimulation = useCallback(async (config = {}) => {
    console.log('startSimulation called, schedule:', schedule);
    if (!schedule || schedule.length === 0) {
      console.error('No schedule data available');
      return;
    }
    
    setStatus('running');
    setScenarios([]);
    setGrade(null);
    
    try {
      // PASO 1: Llamar POST /validate-schedule para registrar el job
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/validate-schedule`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(schedule)
      });
      
      if (!response.ok) {
        throw new Error('Error al registrar el horario para validación');
      }
      
      const { job_id } = await response.json();
      console.log('Job registrado:', job_id);
      
      // PASO 2: Conectar WebSocket con el job_id recibido
      const wsBase = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
      const wsUrl = `${wsBase}/ws/monte-carlo/${job_id}`;
      const websocket = new WebSocket(wsUrl);
      
      websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        setStatus('error');
      };
      
      websocket.onclose = () => {
        console.log('WebSocket cerrado');
      };
      
      websocket.onopen = () => {
        console.log('WebSocket conectado, enviando configuración');
        websocket.send(JSON.stringify({
          n_simulations: config.n_simulations || 1000,
          uncertainty: config.uncertainty || 0.2
        }));
      };
      
      websocket.onmessage = (event) => {
        console.log('WebSocket message:', event.data);
        const data = JSON.parse(event.data);
        
        switch (data.type) {
          case 'started':
            console.log('Simulación iniciada:', data);
            break;
            
          case 'progress':
            setScenarios(prev => [...prev, ...data.scenarios]);
            setProgress({
              completed: data.completed,
              total: data.total,
              feasible_rate: data.feasible_rate
            });
            setGrade(data.grade);
            break;
            
          case 'completed':
            setStatus('completed');
            setGrade(data.final_grade);
            websocket.close();
            break;
            
          case 'error':
            console.error('Error en simulación:', data.message);
            setStatus('error');
            websocket.close();
            break;
        }
      };
      
      setWs(websocket);
    } catch (error) {
      console.error('Error:', error);
      setStatus('error');
    }
  }, [schedule]);

  const stopSimulation = useCallback(() => {
    ws?.close();
    setStatus('idle');
  }, [ws]);

  useEffect(() => {
    return () => ws?.close();
  }, [ws]);

  return {
    scenarios,
    progress,
    grade,
    status,
    startSimulation,
    stopSimulation
  };
}
