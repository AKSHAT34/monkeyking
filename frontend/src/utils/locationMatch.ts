/**
 * Location matching with country→city hierarchy and city aliases.
 * "India" matches "Bangalore, India", "Mumbai", "Bengaluru", etc.
 * "Bangalore" matches "Bengaluru, India"
 * "Remote - India" matches "Remote" or "Remote, India"
 */

const COUNTRY_CITIES: Record<string, string[]> = {
  india: [
    'bangalore', 'bengaluru', 'mumbai', 'bombay', 'delhi', 'new delhi',
    'hyderabad', 'pune', 'chennai', 'madras', 'kolkata', 'calcutta',
    'gurgaon', 'gurugram', 'noida', 'ghaziabad', 'greater noida',
    'ahmedabad', 'jaipur', 'lucknow', 'chandigarh', 'indore', 'bhopal',
    'kochi', 'cochin', 'coimbatore', 'nagpur', 'mysore', 'mysuru',
    'mangalore', 'mangaluru', 'surat', 'vadodara', 'baroda',
    'karnataka', 'maharashtra', 'tamil nadu', 'telangana',
    'andhra pradesh', 'kerala', 'west bengal', 'uttar pradesh',
    'rajasthan', 'gujarat', 'haryana', 'punjab', 'delhi ncr', 'ncr',
  ],
  us: [
    'san francisco', 'new york', 'nyc', 'los angeles', 'la', 'seattle',
    'austin', 'boston', 'chicago', 'denver', 'portland', 'san diego',
    'san jose', 'silicon valley', 'palo alto', 'mountain view',
    'sunnyvale', 'cupertino', 'menlo park', 'washington dc', 'dc',
    'atlanta', 'dallas', 'houston', 'phoenix', 'miami', 'raleigh',
    'california', 'texas', 'washington', 'massachusetts',
  ],
  uk: ['london', 'manchester', 'birmingham', 'edinburgh', 'cambridge', 'oxford', 'bristol'],
  canada: ['toronto', 'vancouver', 'montreal', 'ottawa', 'calgary'],
  singapore: ['singapore'],
  uae: ['dubai', 'abu dhabi'],
  germany: ['berlin', 'munich', 'hamburg', 'frankfurt'],
  australia: ['sydney', 'melbourne', 'brisbane', 'perth'],
};

const CITY_ALIASES: Record<string, string> = {
  bengaluru: 'bangalore', bangalore: 'bengaluru',
  bombay: 'mumbai', mumbai: 'bombay',
  madras: 'chennai', chennai: 'madras',
  calcutta: 'kolkata', kolkata: 'calcutta',
  gurugram: 'gurgaon', gurgaon: 'gurugram',
  cochin: 'kochi', kochi: 'cochin',
  mysuru: 'mysore', mysore: 'mysuru',
  mangaluru: 'mangalore', mangalore: 'mangaluru',
  baroda: 'vadodara', vadodara: 'baroda',
  nyc: 'new york', la: 'los angeles', dc: 'washington dc',
};

const COUNTRY_ALIASES: Record<string, string> = {
  'united states': 'us', usa: 'us', america: 'us',
  'united kingdom': 'uk', britain: 'uk', england: 'uk',
  'united arab emirates': 'uae',
};

function normalize(s: string): string {
  return s.toLowerCase().trim().replace(/\s+/g, ' ');
}

function expandLocation(loc: string): string[] {
  const n = normalize(loc);
  const terms = [n];

  if (n.startsWith('remote')) {
    terms.push('remote');
    return terms;
  }

  const resolved = COUNTRY_ALIASES[n] ?? n;
  if (resolved in COUNTRY_CITIES) {
    terms.push(resolved);
    for (const city of COUNTRY_CITIES[resolved]) terms.push(city);
    return terms;
  }

  if (n in CITY_ALIASES) terms.push(CITY_ALIASES[n]);
  return terms;
}

export function locationMatches(jobLocation: string, preferredLocations: string[]): boolean {
  if (!preferredLocations.length) return true;

  const jobN = normalize(jobLocation);
  if (!jobN) return true; // unknown location = don't filter

  for (const pref of preferredLocations) {
    const prefN = normalize(pref);

    // Remote - Worldwide
    if (prefN === 'remote - worldwide' || prefN === 'remote worldwide') {
      if (jobN.includes('remote')) return true;
      continue;
    }

    // Remote - Country
    if (prefN.startsWith('remote - ') || prefN.startsWith('remote ')) {
      const countryPart = prefN.replace('remote - ', '').replace('remote ', '').trim();
      if (jobN.includes('remote')) {
        const resolved = COUNTRY_ALIASES[countryPart] ?? countryPart;
        if (resolved in COUNTRY_CITIES) {
          const countryTerms = [resolved, ...COUNTRY_CITIES[resolved]];
          if (jobN === 'remote' || jobN === 'remote work') return true;
          for (const term of countryTerms) {
            if (jobN.includes(term)) return true;
          }
        } else {
          if (jobN.includes(countryPart) || jobN === 'remote') return true;
        }
      }
      continue;
    }

    // Plain "Remote"
    if (prefN === 'remote') {
      if (jobN.includes('remote')) return true;
      continue;
    }

    // Standard location
    const expanded = expandLocation(pref);
    for (const term of expanded) {
      if (jobN.includes(term)) return true;
    }
  }

  return false;
}
