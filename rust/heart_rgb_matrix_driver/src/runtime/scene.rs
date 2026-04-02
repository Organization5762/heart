pub const EMPTY_SCENE_MANAGER_ERROR: &str =
    "Scene manager bridge requires at least one scene name.";

#[derive(Clone, Debug)]
pub struct SceneSnapshotCore {
    pub active_scene_index: usize,
    pub active_scene_name: String,
    pub current_button_value: i64,
    pub offset_button_value: Option<i64>,
    pub scene_count: usize,
}

#[derive(Clone, Debug)]
pub struct SceneManagerCore {
    scene_names: Vec<String>,
    offset_button_value: Option<i64>,
}

impl SceneManagerCore {
    pub fn new(scene_names: Vec<String>) -> Result<Self, String> {
        if scene_names.is_empty() {
            return Err(EMPTY_SCENE_MANAGER_ERROR.to_string());
        }
        Ok(Self {
            scene_names,
            offset_button_value: None,
        })
    }

    pub fn active_scene_index(&self, current_button_value: i64) -> Result<usize, String> {
        if self.scene_names.is_empty() {
            return Err(EMPTY_SCENE_MANAGER_ERROR.to_string());
        }
        let offset = self.offset_button_value.unwrap_or_default();
        let count = self.scene_names.len() as i64;
        let raw_index = (current_button_value - offset).rem_euclid(count);
        Ok(raw_index as usize)
    }

    pub fn register_scene(&mut self, scene_name: String) {
        self.scene_names.push(scene_name);
    }

    pub fn reset_button_offset(&mut self, current_button_value: i64) {
        self.offset_button_value = Some(current_button_value);
    }

    pub fn scene_count(&self) -> usize {
        self.scene_names.len()
    }

    pub fn scene_names(&self) -> Vec<String> {
        self.scene_names.clone()
    }

    pub fn snapshot(&self, current_button_value: i64) -> Result<SceneSnapshotCore, String> {
        let active_scene_index = self.active_scene_index(current_button_value)?;
        Ok(SceneSnapshotCore {
            active_scene_index,
            active_scene_name: self.scene_names[active_scene_index].clone(),
            current_button_value,
            offset_button_value: self.offset_button_value,
            scene_count: self.scene_names.len(),
        })
    }
}
