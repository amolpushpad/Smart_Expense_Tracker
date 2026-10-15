import { useEffect, useState } from 'react';
import { profileApi } from '../services/api';

export default function UserAvatar({ user, className = '' }) {
	const [imageUrl, setImageUrl] = useState('');
	const initial = (user?.name || 'U').trim().charAt(0).toUpperCase() || 'U';

	useEffect(() => {
		let objectUrl;
		let active = true;
		setImageUrl('');
		if (!user?.profile_photo_url) return () => { active = false; };
		const controller = new AbortController();
		profileApi.photo(user.profile_photo_url, { signal: controller.signal })
			.then(response => {
				objectUrl = URL.createObjectURL(response.data);
				if (active) setImageUrl(objectUrl);
				else URL.revokeObjectURL(objectUrl);
			})
			.catch(() => {
				if (active) setImageUrl('');
			});
		return () => {
			active = false;
			controller.abort();
			if (objectUrl) URL.revokeObjectURL(objectUrl);
		};
	}, [user?.profile_photo_url]);

	return imageUrl
		? <img className={`user-avatar ${className}`} src={imageUrl} alt={`${user?.name || 'User'} profile`} />
		: <span className={`user-avatar user-avatar-fallback ${className}`} aria-label={`${user?.name || 'User'} profile`}>{initial}</span>;
}
