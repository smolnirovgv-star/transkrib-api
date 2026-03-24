import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ScrollView,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAppTheme } from '../theme';
import { useTranslation } from '../i18n';
import { Language } from '../i18n';
import { resetUrlCache } from '../services/api';
import { GradientBackground } from '../components/GradientBackground';

const LANGUAGES: { key: Language; label: string }[] = [
  { key: 'ru', label: 'RU' },
  { key: 'en', label: 'EN' },
  { key: 'zh', label: 'ZH' },
];

export function SettingsScreen() {
  const { theme } = useAppTheme();
  const { t, language, setLanguage } = useTranslation();

  const [backendUrl, setBackendUrl] = useState('http://localhost:8000');

  useEffect(() => {
    AsyncStorage.getItem('transkrib-backend-url').then((v) => {
      if (v) setBackendUrl(v);
    });
  }, []);

  const handleSave = async () => {
    try {
      await AsyncStorage.setItem('transkrib-backend-url', backendUrl.trim());
      resetUrlCache();
      Alert.alert(t('settingsTitle'), t('save') + ' OK');
    } catch (err: any) {
      Alert.alert(t('error'), err.message || String(err));
    }
  };

  return (
    <GradientBackground>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={[styles.title, { color: theme.text }]}>
          {t('settingsTitle')}
        </Text>

        {/* Backend URL */}
        <View style={[styles.section, { backgroundColor: theme.card, borderColor: theme.border }]}>
          <Text style={[styles.sectionLabel, { color: theme.textSecondary }]}>
            {t('backendUrl')}
          </Text>
          <TextInput
            style={[
              styles.input,
              {
                backgroundColor: theme.inputBackground,
                color: theme.text,
                borderColor: theme.border,
              },
            ]}
            value={backendUrl}
            onChangeText={setBackendUrl}
            placeholder="http://localhost:8000"
            placeholderTextColor={theme.textSecondary}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
          />
        </View>

        {/* Language */}
        <View style={[styles.section, { backgroundColor: theme.card, borderColor: theme.border }]}>
          <Text style={[styles.sectionLabel, { color: theme.textSecondary }]}>
            {t('language')}
          </Text>
          <View style={styles.langRow}>
            {LANGUAGES.map((lang) => (
              <TouchableOpacity
                key={lang.key}
                style={[
                  styles.langButton,
                  {
                    backgroundColor:
                      language === lang.key ? theme.primary : theme.inputBackground,
                    borderColor:
                      language === lang.key ? theme.primary : theme.border,
                  },
                ]}
                onPress={() => setLanguage(lang.key)}
                activeOpacity={0.7}
              >
                <Text
                  style={[
                    styles.langButtonText,
                    {
                      color: language === lang.key ? '#fff' : theme.text,
                    },
                  ]}
                >
                  {lang.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Save */}
        <TouchableOpacity
          style={[styles.saveButton, { backgroundColor: theme.primary }]}
          onPress={handleSave}
          activeOpacity={0.7}
        >
          <Text style={styles.saveButtonText}>{t('save')}</Text>
        </TouchableOpacity>
      </ScrollView>
    </GradientBackground>
  );
}

const styles = StyleSheet.create({
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 20,
    paddingTop: 60,
    paddingBottom: 40,
  },
  title: {
    fontSize: 24,
    fontWeight: '800',
    marginBottom: 24,
  },
  section: {
    padding: 16,
    borderRadius: 14,
    borderWidth: 1,
    marginBottom: 16,
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 10,
  },
  input: {
    height: 48,
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 14,
    fontSize: 15,
  },
  langRow: {
    flexDirection: 'row',
    gap: 10,
  },
  langButton: {
    flex: 1,
    height: 44,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  langButtonText: {
    fontSize: 15,
    fontWeight: '700',
  },
  saveButton: {
    height: 50,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 8,
  },
  saveButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
});
