import { DragAndDropProvider } from '../context/DragAndDropContext';
import { BusColumn } from './dnd/BusColumn';

export function DraggableSchedule({ 
  schedule, 
  onScheduleChange, 
  selectedRouteId, 
  onRouteSelect 
}) {
  const handleScheduleChange = (newSchedule) => {
    onScheduleChange(newSchedule);
  };

  if (!schedule || schedule.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-[13px] text-zinc-500 font-medium">Sin datos</p>
          <p className="text-[11px] text-zinc-600 mt-1">
            No hay horarios disponibles para mostrar
          </p>
        </div>
      </div>
    );
  }

  return (
    <DragAndDropProvider schedule={schedule} onScheduleChange={handleScheduleChange}>
      <div className="flex gap-4 overflow-x-auto pb-4 h-full">
        {schedule.map((bus) => (
          <BusColumn 
            key={bus.bus_id} 
            bus={bus}
            selectedRouteId={selectedRouteId}
            onRouteSelect={onRouteSelect}
          />
        ))}
      </div>
    </DragAndDropProvider>
  );
}
