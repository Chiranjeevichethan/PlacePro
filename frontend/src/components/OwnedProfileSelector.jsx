import { useStudentProfileContext } from '../hooks/useStudentProfileContext';
export default function OwnedProfileSelector({ onNewProfile }) {
  const { profileId, ownedProfileIds, selectProfile, listLoading, profile } = useStudentProfileContext();
  return <div className="owned-profile-selector">
    <label htmlFor="owned-profile">Profile</label>
    <select id="owned-profile" aria-label="Active student profile" value={profileId || ''}
      disabled={listLoading} onChange={(event) => selectProfile(event.target.value)}>
      <option value="" disabled>{listLoading ? 'Loading profiles…' : 'Select a profile'}</option>
      {ownedProfileIds.map((id, index) => <option key={id} value={id}>
        {id === profileId && profile?.name ? profile.name : `Profile ${index + 1}`} · {id.slice(0, 8)}
      </option>)}
    </select>
    <button type="button" className="dash-btn secondary" onClick={onNewProfile}>New profile</button>
  </div>;
}
