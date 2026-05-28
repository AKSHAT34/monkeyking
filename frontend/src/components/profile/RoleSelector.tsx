'use client';

interface RoleSelectorProps {
  suggestedRoles: string[];
  selectedRoles: string[];
  onChange: (roles: string[]) => void;
}

export function RoleSelector({ suggestedRoles, selectedRoles, onChange }: RoleSelectorProps) {
  const allRoles = Array.from(new Set([...selectedRoles, ...suggestedRoles]));

  const toggle = (role: string) => {
    if (selectedRoles.includes(role)) {
      onChange(selectedRoles.filter((r) => r !== role));
    } else {
      onChange([...selectedRoles, role]);
    }
  };

  if (allRoles.length === 0) {
    return <p className="text-gray-500 text-sm">No roles suggested yet. Upload a CV to get AI suggestions.</p>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {allRoles.map((role) => {
        const isSelected = selectedRoles.includes(role);
        return (
          <button
            key={role}
            type="button"
            onClick={() => toggle(role)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors border ${
              isSelected
                ? 'bg-mk-orange text-white border-mk-orange'
                : 'bg-mk-card text-gray-400 border-mk-border hover:border-gray-500'
            }`}
          >
            {role}
          </button>
        );
      })}
    </div>
  );
}
