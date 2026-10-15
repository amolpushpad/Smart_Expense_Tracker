import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getApiErrorMessage, profileApi } from '../services/api';
import PageHeader from '../components/PageHeader';
import UserAvatar from '../components/UserAvatar';
import '../styles/profile.css';

const blankProfile = {
	name: '',
	username: '',
	email: '',
	date_of_birth: '',
	phone_number: '',
	gender: '',
	bio: '',
};

function apiError(error) {
	const fieldErrors = error.response?.data?.errors;
	return fieldErrors ? Object.values(fieldErrors).join(' ') : getApiErrorMessage(error);
}

function formatCreatedAt(value) {
	if (!value) return 'Not available';
	const parsed = new Date(value);
	return Number.isNaN(parsed.valueOf()) ? 'Not available' : parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
}

export default function Profile() {
	const { user: authUser, refreshProfile, logout } = useAuth();
	const navigate = useNavigate();
	const [profile, setProfile] = useState(blankProfile);
	const [createdAt, setCreatedAt] = useState('');
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [uploading, setUploading] = useState(false);
	const [removingPhoto, setRemovingPhoto] = useState(false);
	const [error, setError] = useState('');
	const [notice, setNotice] = useState('');
	const [currentPassword, setCurrentPassword] = useState('');
	const [currentPasswordForChange, setCurrentPasswordForChange] = useState('');
	const [newPassword, setNewPassword] = useState('');
	const [photoPreview, setPhotoPreview] = useState('');
	const [photoFile, setPhotoFile] = useState(null);
	const [passwordError, setPasswordError] = useState('');
	const [passwordNotice, setPasswordNotice] = useState('');
	const [changingPassword, setChangingPassword] = useState(false);

	useEffect(() => {
		const controller = new AbortController();
		profileApi.get({ signal: controller.signal })
			.then(response => {
				const user = response.data.data.user;
				setProfile({
					name: user.name || '',
					username: user.username || '',
					email: user.email || '',
					date_of_birth: user.date_of_birth || '',
					phone_number: user.phone_number || '',
					gender: user.gender || '',
					bio: user.bio || '',
				});
				setCreatedAt(user.created_at || '');
			})
			.catch(requestError => {
				if (requestError.name !== 'CanceledError') setError(getApiErrorMessage(requestError));
			})
			.finally(() => { if (!controller.signal.aborted) setLoading(false); });
		return () => controller.abort();
	}, []);

	useEffect(() => () => {
		if (photoPreview) URL.revokeObjectURL(photoPreview);
	}, [photoPreview]);

	const updateField = event => {
		const { name, value } = event.target;
		setProfile(current => ({ ...current, [name]: value }));
	};

	const saveProfile = async event => {
		event.preventDefault();
		setSaving(true);
		setError('');
		setNotice('');
		const payload = { ...profile };
		if (profile.email !== authUser?.email) payload.current_password = currentPassword;
		try {
			await profileApi.update(payload);
			await refreshProfile();
			setCurrentPassword('');
			setNotice('Your profile was updated.');
		} catch (requestError) {
			setError(apiError(requestError));
		} finally {
			setSaving(false);
		}
	};

	const choosePhoto = event => {
		const file = event.target.files?.[0];
		if (!file) return;
		if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
			setPhotoFile(null);
			setPhotoPreview('');
			setError('Choose a JPEG, PNG, or WebP image.');
			event.target.value = '';
			return;
		}
		if (file.size > 5 * 1024 * 1024) {
			setPhotoFile(null);
			setPhotoPreview('');
			setError('Profile photos must be 5 MB or smaller.');
			event.target.value = '';
			return;
		}
		setError('');
		setPhotoFile(file);
		setPhotoPreview(URL.createObjectURL(file));
	};

	const uploadPhoto = async () => {
		if (!photoFile) return;
		setUploading(true);
		setError('');
		setNotice('');
		try {
			await profileApi.uploadPhoto(photoFile);
			await refreshProfile();
			setPhotoFile(null);
			setPhotoPreview('');
			setNotice('Your profile photo was updated.');
		} catch (requestError) {
			setError(apiError(requestError));
		} finally {
			setUploading(false);
		}
	};

	const removePhoto = async () => {
		setRemovingPhoto(true);
		setError('');
		setNotice('');
		try {
			await profileApi.removePhoto();
			await refreshProfile();
			setPhotoFile(null);
			setPhotoPreview('');
			setNotice('Your profile photo was removed.');
		} catch (requestError) {
			setError(apiError(requestError));
		} finally {
			setRemovingPhoto(false);
		}
	};

	const changePassword = async event => {
		event.preventDefault();
		setChangingPassword(true);
		setPasswordError('');
		setPasswordNotice('');
		try {
			const response = await profileApi.changePassword({ current_password: currentPasswordForChange, new_password: newPassword });
			setPasswordNotice(response.data.message || 'Password changed successfully.');
			setCurrentPasswordForChange('');
			setNewPassword('');
		} catch (requestError) {
			setPasswordError(apiError(requestError));
		} finally {
			setChangingPassword(false);
		}
	};

	return <section className="profile-page">
		<PageHeader title="Profile" description="View your personal details and manage account security." />
		{error && <div className="profile-alert error" role="alert">{error}</div>}
		{notice && <div className="profile-alert success" role="status">{notice}</div>}
		{loading ? <div className="profile-loading" role="status">Loading your profile…</div> : <div className="profile-layout">
			<section className="profile-card profile-photo-card" aria-labelledby="photo-heading">
				<h3 id="photo-heading">Profile photo</h3>
				<div className="profile-photo-preview">
					{photoPreview
						? <img src={photoPreview} alt="Preview of the selected profile photo" />
						: <UserAvatar user={authUser} className="profile-large-avatar" />}
				</div>
				<p className="profile-muted">JPEG, PNG, or WebP. Maximum 5 MB.</p>
				<label className="profile-file-button">Choose photo<input type="file" accept="image/jpeg,image/png,image/webp" onChange={choosePhoto} /></label>
				{photoFile && <button className="profile-primary" type="button" disabled={uploading} onClick={uploadPhoto}>{uploading ? 'Uploading…' : 'Save new photo'}</button>}
				{authUser?.profile_photo_url && <button className="profile-text-button destructive" type="button" disabled={removingPhoto} onClick={removePhoto}>{removingPhoto ? 'Removing…' : 'Remove photo'}</button>}
			</section>

			<section className="profile-card">
				<h3>Personal information</h3>
				<form className="profile-form" onSubmit={saveProfile}>
					<label>Full name<input name="name" autoComplete="name" maxLength="120" required value={profile.name} onChange={updateField} /></label>
					<label>Username<input name="username" autoComplete="username" minLength="3" maxLength="30" pattern="[A-Za-z0-9_.-]{3,30}" placeholder="Optional" value={profile.username} onChange={updateField} /><small>3–30 letters, numbers, dots, underscores, or hyphens.</small></label>
					<label>Email address<input name="email" type="email" autoComplete="email" maxLength="254" required value={profile.email} onChange={updateField} /></label>
					{profile.email !== authUser?.email && <label className="profile-wide">Current password to confirm email change<input type="password" autoComplete="current-password" value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} required /></label>}
					<label>Date of birth (optional)<input name="date_of_birth" type="date" max={new Date().toISOString().slice(0, 10)} value={profile.date_of_birth} onChange={updateField} /></label>
					<label>Phone number (optional)<input name="phone_number" type="tel" autoComplete="tel" maxLength="30" value={profile.phone_number} onChange={updateField} /></label>
					<label>Gender (optional)<input name="gender" maxLength="40" value={profile.gender} onChange={updateField} /></label>
					<label className="profile-wide">Short bio (optional)<textarea name="bio" rows="4" maxLength="500" value={profile.bio} onChange={updateField} /></label>
					<div className="profile-wide profile-actions"><button className="profile-primary" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save profile'}</button></div>
				</form>
			</section>

			<section className="profile-card profile-account-card">
				<h3>Account information</h3>
				<dl><div><dt>Account created</dt><dd>{formatCreatedAt(createdAt)}</dd></div><div><dt>Email</dt><dd>{profile.email}</dd></div></dl>
				<p className="profile-muted">Email verification is not currently part of this application.</p>
			</section>

			<section className="profile-card profile-security-card" id="security">
				<h3>Account &amp; security</h3>
				<p className="profile-muted">Choose a unique password you do not use elsewhere.</p>
				{passwordError && <div className="profile-alert error" role="alert">{passwordError}</div>}
				{passwordNotice && <div className="profile-alert success" role="status">{passwordNotice}</div>}
				<form className="profile-form profile-password-form" onSubmit={changePassword}>
					<label>Current password<input type="password" autoComplete="current-password" required value={currentPasswordForChange} onChange={event => setCurrentPasswordForChange(event.target.value)} /></label>
					<label>New password<input type="password" autoComplete="new-password" minLength="8" maxLength="128" required value={newPassword} onChange={event => setNewPassword(event.target.value)} /><small>Must be 8–128 characters.</small></label>
					<div className="profile-actions"><button className="profile-primary" type="submit" disabled={changingPassword}>{changingPassword ? 'Changing…' : 'Change password'}</button></div>
				</form>
				<button className="profile-text-button" type="button" onClick={async () => { if (await logout()) navigate('/login'); }}>Log out</button>
			</section>
		</div>}
	</section>;
}
